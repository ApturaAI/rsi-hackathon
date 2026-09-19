"""`stbench eval`: run the learner on tasks with and without a skill, then score.

Arms differ only by the mounted skill folder: `baseline` (none), `placebo` (a
generic content-free skill) and `skill`. All learner calls go through one
metering gateway; grader / simulated-user calls through a second one.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from pathlib import Path

import httpx

from . import harbor
from .config import HackathonCfg, learner_settings, task_names
from .gateway import AttemptTagRegistry, BudgetMeter, Ledger, LocalGatewayServer, build_app, fetch_prices, tagged
from .scoring import Pair, summarize
from .tasks import Task, is_pass, load_task, score

ARMS = ("baseline", "placebo", "skill")
_RETRY_DELAYS = (0.5, 2.0, 5.0)  # transient upstream/Docker failures often clear within seconds

_PLACEBO_SKILL = (
    "---\nname: placebo\ndescription: generic problem-solving guidance (control arm)\n---\n"
    "Read the problem carefully. Work through it step by step and show your reasoning. "
    "Double-check your arithmetic. End with a line: #### <answer>.\n"
)


def write_placebo(placebo_dir: Path) -> Path:
    placebo_dir.mkdir(parents=True, exist_ok=True)
    (placebo_dir / "SKILL.md").write_text(_PLACEBO_SKILL)
    return placebo_dir


async def _attempt_with_retries(task: Task, skill_dir: Path | None, sem: asyncio.Semaphore, *,
                                registry: AttemptTagRegistry | None, tags: dict, **run_kw) -> dict:
    """One scored attempt; retries infrastructure failures, never a wrong answer."""
    judged = task.benchmark == "healthbench"
    for n, delay in enumerate((0.0, *_RETRY_DELAYS)):
        if delay:
            await asyncio.sleep(delay)
        attempt_id = secrets.token_urlsafe(24) if judged else ""
        registration = registry.registered(attempt_id, **tags) if judged and registry else None
        if registration is not None:
            registration.__enter__()
        try:
            async with sem:
                attempt = await harbor.run_attempt(task, skill_dir, attempt_id=attempt_id, **run_kw)
        finally:
            if registration is not None:
                registration.__exit__(None, None, None)
        status = attempt.get("status")
        blocked = status == "budget_exhausted"
        ok_statuses = {"ok", "invalid_output"} if judged else {"ok"}
        error = None if status in ok_statuses or blocked else f"{task.benchmark}_runtime_{status}"
        if not error or blocked or n == len(_RETRY_DELAYS):
            return {**attempt, "blocked": blocked, "error": error}
    raise AssertionError("unreachable")


async def run_eval(cfg: HackathonCfg, domain_name: str, *, skill_dir: str | Path | None, out: str | Path,
                   arms: list[str], task_ids: list[str] | None = None, limit: int | None = None,
                   upstream_base_url: str, upstream_key: str | None, concurrency: int | None = None) -> dict:
    domain = cfg.domain(domain_name)
    if not arms or any(a not in ARMS for a in arms):
        raise ValueError(f"arms must be drawn from {ARMS}, got {arms}")
    if "skill" in arms and not skill_dir:
        raise ValueError("the skill arm needs --skill")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    settings = learner_settings(cfg, domain)
    names = task_names(domain, task_ids=task_ids, limit=limit)
    tasks = [load_task(domain.benchmark, domain.dataset_dir, n) for n in names]
    skill_path = Path(skill_dir).resolve() if skill_dir else None
    arm_dirs = {"baseline": None, "skill": skill_path}
    if "placebo" in arms:
        arm_dirs["placebo"] = write_placebo(out / "placebo_skill")

    headers = {"authorization": f"Bearer {upstream_key}"} if upstream_key else {}
    upstream = httpx.AsyncClient(base_url=upstream_base_url, headers=headers, timeout=600.0)
    prices = await fetch_prices(upstream)
    learner_meter, learner_ledger = BudgetMeter(domain.eval_budget_tokens), Ledger()
    learner_gw = await LocalGatewayServer(build_app(learner_meter, client=upstream, ledger=learner_ledger,
                                                    prices=prices)).start()
    needs_aux = domain.benchmark != "qfbench"
    aux_meter = aux_ledger = aux_registry = aux_key = aux_gw = aux_exhausted = None
    if needs_aux:
        aux_meter, aux_ledger, aux_registry = BudgetMeter(domain.judge_budget_tokens), Ledger(), AttemptTagRegistry()
        aux_key = secrets.token_urlsafe(32)
        aux_app = build_app(aux_meter, client=upstream, ledger=aux_ledger, virtual_key=aux_key,
                            attempt_registry=aux_registry, prices=prices)
        aux_gw = await LocalGatewayServer(aux_app).start()
        if domain.benchmark == "healthbench":
            aux_exhausted = lambda: bool(aux_app.state.budget_rejected)  # noqa: E731
        else:
            aux_exhausted = aux_meter.exhausted

    sem = asyncio.Semaphore(concurrency or cfg.concurrency)
    rows: list[dict] = []

    async def _arm(task: Task, arm: str) -> float | None:
        with tagged(phase="eval", arm=arm, task_id=task.id):
            attempt = await _attempt_with_retries(
                task, arm_dirs[arm], sem,
                registry=aux_registry, tags={"phase": "eval", "arm": arm, "task_id": task.id},
                settings=settings, gateway_url=learner_gw.container_url, gateway_key="stbench-no-secret",
                jobs_dir=out / "harbor-jobs",
                aux_url=aux_gw.container_url if aux_gw else None, aux_key=aux_key,
                aux_exhausted=None if task.benchmark == "healthbench" else aux_exhausted,
            )
        value = score(task, attempt)
        if aux_exhausted is not None and aux_exhausted():
            raise RuntimeError("grader/simulator budget pool exhausted; results would be false zeros")
        if attempt["blocked"]:
            raise RuntimeError("learner budget pool exhausted mid-evaluation (gateway 402): "
                               "results would be false failures — raise eval_budget_tokens")
        if attempt["error"]:
            detail = attempt.get("artifacts", {}).get("stderr_tail") or ""
            raise RuntimeError(f"attempt failed after retries ({attempt['error']}) for {task.name!r} arm {arm!r}: "
                               "an upstream/gateway/Docker problem, not a learner mistake"
                               f"\n  error_class: {attempt.get('error_class')}"
                               + (f"\n  harbor stderr (tail):\n{detail}" if detail else ""))
        rows.append({"task_id": task.id, "task_name": task.name, "arm": arm, "score": value,
                     "passed": None if value is None else is_pass(value), "answer": attempt.get("answer", ""),
                     "status": attempt.get("status"), "trial_dir": attempt.get("artifacts", {}).get("trial_dir")})
        return value

    async def _task(task: Task) -> Pair:
        results = await asyncio.gather(*[_arm(task, arm) for arm in arms])
        by_arm = dict(zip(arms, results))
        return Pair(task_id=task.id, seed=0, baseline=by_arm.get("baseline"), placebo=by_arm.get("placebo"),
                    skill=by_arm.get("skill"), domain=task.benchmark,
                    invalidated=frozenset(a for a in arms if by_arm[a] is None))

    try:
        pairs = await asyncio.gather(*[_task(t) for t in tasks])
    finally:
        await learner_gw.stop()
        if aux_gw is not None:
            await aux_gw.stop()
        await upstream.aclose()
        (out / "learner_ledger.jsonl").write_text(learner_ledger.to_jsonl())
        if aux_ledger is not None:
            (out / "grader_ledger.jsonl").write_text(aux_ledger.to_jsonl())
        (out / "attempts.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    by_id = {t.id: t.name for t in tasks}
    summary = summarize(list(pairs))
    result = {
        "domain": domain.name,
        "benchmark": domain.benchmark,
        "learner": {"model": settings.model, "agent": settings.agent, "agent_kwargs": settings.agent_kwargs},
        "skill_dir": str(skill_path) if skill_path else None,
        "arms": arms,
        "tasks": names,
        "summary": summary,
        "per_task": [{**r, "task_name": by_id.get(r["task_id"], r["task_id"])} for r in summary["per_task"]],
        "learner_usage": learner_meter.usage(),
        "learner_cost": learner_ledger.summary()["cost"],
        "grader_usage": aux_meter.usage() if aux_meter else None,
        "grader_cost": aux_ledger.summary()["cost"] if aux_ledger else None,
        "note": "local evaluation on training tasks; the leaderboard scores private held-out tasks",
    }
    (out / "eval_result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


def format_result(result: dict) -> str:
    s = result["summary"]
    lines = [f"{result['domain']} ({result['benchmark']}) · learner {result['learner']['model']} "
             f"via {result['learner']['agent']} · {s.get('n_tasks')} tasks"]
    for key in ("baseline_rate", "placebo_rate", "skill_rate", "delta", "net_delta", "ci95", "note"):
        if s.get(key) is not None:
            lines.append(f"  {key:<14} {s[key]}")
    for who in ("learner", "grader"):
        usage = result.get(f"{who}_usage")
        if usage:
            usd = (result.get(f"{who}_cost") or {}).get("estimated_usd")
            cost = f" · ${usd:.4f}" if usd is not None else ""
            lines.append(f"  {who} tokens {usage['total_tokens']}{cost}")
    return "\n".join(lines)
