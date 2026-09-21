"""Read local run/audit/experiment files for the research dashboard."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.lib import DOMAINS, REPO_ROOT, read_json, read_jsonl

LEAK_KEYS = frozenset({
    "answer",
    "criterion",
    "explanation",
    "expected_actions",
    "rationale",
    "original_answer",
    "question",
    "rubrics",
    "reference_data",
    "gold",
    "canonical_answer",
})


def _mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _safe(v) for k, v in obj.items() if k not in LEAK_KEYS}
    if isinstance(obj, list):
        return [_safe(v) for v in obj]
    return obj


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _usd(block: Any) -> float | None:
    if not isinstance(block, dict):
        return None
    return _num(block.get("estimated_usd"))


def _tokens(block: Any) -> int | None:
    if not isinstance(block, dict):
        return None
    value = block.get("total_tokens")
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        value = read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _load_json_any(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        return [row for row in read_jsonl(path) if isinstance(row, dict) and not row.get("_parser_error")]
    except (OSError, UnicodeError):
        return []


def _task_index() -> dict[str, dict]:
    rows = _load_jsonl(REPO_ROOT / "research" / "data" / "task_index.jsonl")
    by_name: dict[str, dict] = {}
    for row in rows:
        name = row.get("task_name")
        if isinstance(name, str):
            by_name[name] = {
                "stratum": row.get("stratum"),
                "theme": row.get("theme"),
                "category": row.get("category"),
                "difficulty": row.get("difficulty"),
                "reward_basis": row.get("reward_basis"),
                "domain": row.get("domain"),
            }
    return by_name


def _theme_from_attempt(row: dict) -> str | None:
    verifier = row.get("verifier") if isinstance(row.get("verifier"), dict) else {}
    metrics = verifier.get("metrics") if isinstance(verifier.get("metrics"), dict) else {}
    for key in metrics:
        if isinstance(key, str) and key.startswith("theme:"):
            return key.split(":", 1)[1]
    return None


def _official_rates(eval_result: dict) -> dict[str, float | None]:
    summary = eval_result.get("summary") if isinstance(eval_result.get("summary"), dict) else {}
    # Top-level official rates. Do not fall back to by_domain.skill_rate, which is 0.0
    # when the skill arm was not run.
    return {
        "baseline": _num(summary.get("baseline_rate")),
        "placebo": _num(summary.get("placebo_rate")),
        "skill": _num(summary.get("skill_rate")),
        "delta": _num(summary.get("delta")),
        "net_delta": _num(summary.get("net_delta")),
        "n_tasks": summary.get("n_tasks") if isinstance(summary.get("n_tasks"), int) else None,
        "official_note": summary.get("note"),
        "official_arms": summary.get("arms") if isinstance(summary.get("arms"), list) else None,
    }


def _pass_rate(rows: list[dict], arm: str) -> float | None:
    scores = [
        row for row in rows
        if row.get("arm") == arm and row.get("outcome_class") == "learner_outcome"
        and isinstance(row.get("passed"), bool)
    ]
    if not scores:
        return None
    return round(sum(1 for row in scores if row["passed"]) / len(scores), 4)


def _pair_tasks(eval_result: dict, attempts: list[dict]) -> list[dict]:
    """Task-level official scores, with derived deltas from those official values."""
    summary = eval_result.get("summary") if isinstance(eval_result.get("summary"), dict) else {}
    official_rows = summary.get("per_task") if isinstance(summary.get("per_task"), list) else []
    names = {
        row.get("task_id"): row.get("task_name")
        for row in (eval_result.get("per_task") or [])
        if isinstance(row, dict)
    }
    outcomes: dict[tuple[str, str], str] = {}
    meta: dict[str, dict] = {}
    for row in attempts:
        tid = str(row.get("task_id") or "")
        arm = str(row.get("arm") or "")
        if tid and arm:
            outcomes[(tid, arm)] = str(row.get("outcome_class") or "")
        if tid and tid not in meta:
            meta[tid] = {
                "task_name": row.get("task_name"),
                "stratum": row.get("stratum") or row.get("theme"),
            }
    pairs = []
    for row in official_rows:
        if not isinstance(row, dict):
            continue
        tid = str(row.get("task_id") or "")
        placebo = _num(row.get("placebo"))
        skill = _num(row.get("skill"))
        control = "placebo" if placebo is not None and skill is not None else None
        left = placebo
        delta = None
        if control and left is not None and skill is not None:
            skill_ok = outcomes.get((tid, "skill"), "learner_outcome") == "learner_outcome"
            ctrl_ok = outcomes.get((tid, "placebo"), "learner_outcome") == "learner_outcome"
            if skill_ok and ctrl_ok:
                delta = round(skill - left, 6)
            else:
                control = None
        pairs.append({
            "task_id": tid,
            "task_name": names.get(tid) or (meta.get(tid) or {}).get("task_name"),
            "placebo": placebo,
            "skill": skill,
            "control": control,
            "delta": delta,
            "stratum": (meta.get(tid) or {}).get("stratum"),
            "change": (
                "improved" if delta is not None and delta > 1e-9
                else "regressed" if delta is not None and delta < -1e-9
                else "unchanged" if delta is not None
                else None
            ),
        })
    return pairs


def _stratum_rollups(pairs: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in pairs:
        if row.get("delta") is None:
            continue
        buckets[str(row.get("stratum") or "unknown")].append(row)
    out = []
    for name, rows in sorted(buckets.items()):
        control = rows[0].get("control")
        lefts = [r["placebo"] for r in rows if r.get("placebo") is not None]
        skills = [r["skill"] for r in rows if r.get("skill") is not None]
        out.append({
            "stratum": name,
            "n_tasks": len(rows),
            "control": control,
            "control_mean": round(sum(lefts) / len(lefts), 4) if lefts else None,
            "skill_mean": round(sum(skills) / len(skills), 4) if skills else None,
            "delta": round((sum(skills) / len(skills)) - (sum(lefts) / len(lefts)), 4)
            if lefts and skills else None,
            "improved": sum(1 for r in rows if r["change"] == "improved"),
            "regressed": sum(1 for r in rows if r["change"] == "regressed"),
            "unchanged": sum(1 for r in rows if r["change"] == "unchanged"),
        })
    return out


def _discover_run_names() -> list[str]:
    names: set[str] = set()
    runs = REPO_ROOT / "runs"
    if runs.is_dir():
        for path in runs.iterdir():
            if path.is_dir() and (path / "eval_result.json").is_file():
                names.add(path.name)
    reports = REPO_ROOT / "research" / "reports"
    if reports.is_dir():
        for path in reports.iterdir():
            if path.is_dir() and ((path / "summary.json").is_file() or (path / "attempts.jsonl").is_file()):
                names.add(path.name)
    return sorted(names)


def _attempts_for(name: str) -> list[dict]:
    parsed = REPO_ROOT / "research" / "reports" / name / "attempts.jsonl"
    raw = REPO_ROOT / "runs" / name / "attempts.jsonl"
    rows = _load_jsonl(parsed) or _load_jsonl(raw)
    index = _task_index()
    cleaned = []
    for row in rows:
        item = _safe(row)
        task_name = item.get("task_name")
        meta = index.get(task_name) if isinstance(task_name, str) else None
        if meta:
            item.setdefault("stratum", meta.get("stratum") or meta.get("theme") or meta.get("category"))
            item.setdefault("theme", meta.get("theme"))
            item.setdefault("category", meta.get("category"))
            item.setdefault("difficulty", meta.get("difficulty"))
            item.setdefault("reward_basis", meta.get("reward_basis"))
        if not item.get("theme"):
            item["theme"] = _theme_from_attempt(item)
            item.setdefault("stratum", item.get("theme"))
        if item.get("outcome_class") is None:
            item["outcome_class"] = "learner_outcome" if item.get("status") in {None, "ok", "invalid_output"} else "parser_failure"
        cleaned.append(item)
    return cleaned


def load_run(name: str) -> dict | None:
    eval_result = _load_json(REPO_ROOT / "runs" / name / "eval_result.json")
    parsed = _load_json(REPO_ROOT / "research" / "reports" / name / "summary.json")
    if eval_result is None and parsed is None:
        return None
    eval_result = eval_result or {}
    rates = _official_rates(eval_result) if eval_result else {
        "baseline": (parsed or {}).get("official_summary", {}).get("baseline_rate") if parsed else None,
        "placebo": (parsed or {}).get("official_summary", {}).get("placebo_rate") if parsed else None,
        "skill": (parsed or {}).get("official_summary", {}).get("skill_rate") if parsed else None,
        "delta": (parsed or {}).get("official_summary", {}).get("delta") if parsed else None,
        "net_delta": (parsed or {}).get("official_summary", {}).get("net_delta") if parsed else None,
        "n_tasks": (parsed or {}).get("official_summary", {}).get("n_tasks") if parsed else None,
        "official_note": (parsed or {}).get("official_summary", {}).get("note") if parsed else None,
        "official_arms": (parsed or {}).get("arms") if parsed else None,
    }
    if parsed and eval_result is None:
        rates = {
            "baseline": _num((parsed.get("official_summary") or {}).get("baseline_rate")),
            "placebo": _num((parsed.get("official_summary") or {}).get("placebo_rate")),
            "skill": _num((parsed.get("official_summary") or {}).get("skill_rate")),
            "delta": _num((parsed.get("official_summary") or {}).get("delta")),
            "net_delta": _num((parsed.get("official_summary") or {}).get("net_delta")),
            "n_tasks": (parsed.get("official_summary") or {}).get("n_tasks"),
            "official_note": (parsed.get("official_summary") or {}).get("note"),
            "official_arms": parsed.get("arms"),
        }
    attempts = _attempts_for(name)
    arms = [a for a in (eval_result.get("arms") or (parsed or {}).get("arms") or []) if a in ("placebo", "skill")]
    if not arms:
        # Fall back to arms present in attempts when eval_result omits them.
        seen = {str(row.get("arm") or "") for row in attempts}
        arms = [a for a in ("placebo", "skill") if a in seen]
    attempts = [row for row in attempts if str(row.get("arm") or "") in {"placebo", "skill"}]
    learner = eval_result.get("learner") or (parsed or {}).get("learner") or {}
    learner_cost = _usd(eval_result.get("learner_cost") or (parsed or {}).get("learner_cost"))
    grader_cost = _usd(eval_result.get("grader_cost") or (parsed or {}).get("grader_cost"))
    n_tasks = rates.get("n_tasks") or len(eval_result.get("tasks") or []) or None
    total_cost = None
    if learner_cost is not None or grader_cost is not None:
        total_cost = round((learner_cost or 0) + (grader_cost or 0), 6)
    pairs = _pair_tasks(eval_result, attempts) if eval_result else []
    comparable = [p for p in pairs if p.get("delta") is not None]
    outcome_counts: dict[str, int] = defaultdict(int)
    for row in attempts:
        outcome_counts[str(row.get("outcome_class") or "unknown")] += 1

    return {
        "name": name,
        "run_dir": f"runs/{name}",
        "domain": eval_result.get("domain") or (parsed or {}).get("domain"),
        "benchmark": eval_result.get("benchmark") or (parsed or {}).get("benchmark"),
        "learner": learner.get("model") if isinstance(learner, dict) else None,
        "agent": learner.get("agent") if isinstance(learner, dict) else None,
        "skill_dir": eval_result.get("skill_dir") or (parsed or {}).get("skill_dir"),
        "arms": arms,
        "n_tasks": n_tasks,
        "n_attempts": len(attempts),
        "placebo": rates.get("placebo"),
        "skill": rates.get("skill"),
        "net_delta": rates.get("net_delta"),
        "official_note": rates.get("official_note"),
        "learner_tokens": _tokens(eval_result.get("learner_usage") or (parsed or {}).get("learner_usage")),
        "grader_tokens": _tokens(eval_result.get("grader_usage") or (parsed or {}).get("grader_usage")),
        "learner_cost": learner_cost,
        "grader_cost": grader_cost,
        "total_cost": total_cost,
        "cost_per_task": round(total_cost / n_tasks, 6) if total_cost is not None and n_tasks else None,
        "mtime": _mtime(REPO_ROOT / "runs" / name / "eval_result.json")
        or _mtime(REPO_ROOT / "research" / "reports" / name / "summary.json"),
        "has_official": bool(eval_result),
        "has_parsed": bool(parsed),
        "outcome_counts": dict(outcome_counts),
        "attempts": attempts,
        "pairs": pairs,
        "comparison": {
            "mean_score": {
                "placebo": rates.get("placebo"),
                "skill": rates.get("skill"),
            },
            "pass_rate": {arm: _pass_rate(attempts, arm) for arm in ("placebo", "skill")},
            "official": rates,
            "skill_minus_placebo": rates.get("net_delta"),
            "derived_from": "official eval_result.json rates; pass rate and task deltas from official per-task scores (placebo vs skill only)",
        },
        "regressions": {
            "improved": [p for p in comparable if p["change"] == "improved"],
            "regressed": [p for p in comparable if p["change"] == "regressed"],
            "unchanged": [p for p in comparable if p["change"] == "unchanged"],
            "excluded_non_learner": [
                p for p in pairs
                if p.get("skill") is not None and p.get("placebo") is not None
                and p.get("delta") is None
            ],
            "by_stratum": _stratum_rollups(pairs),
        },
        "tasks": eval_result.get("tasks") or (parsed or {}).get("tasks") or [],
    }


def list_runs() -> list[dict]:
    summaries = []
    for name in _discover_run_names():
        run = load_run(name)
        if not run:
            continue
        summaries.append({k: run[k] for k in (
            "name", "run_dir", "domain", "benchmark", "learner", "agent", "skill_dir",
            "arms", "n_tasks", "n_attempts", "placebo", "skill",
            "net_delta", "official_note", "learner_tokens", "grader_tokens",
            "learner_cost", "grader_cost", "total_cost", "cost_per_task", "mtime",
            "has_official", "has_parsed", "outcome_counts",
        )})
    summaries.sort(key=lambda r: r.get("mtime") or "", reverse=True)
    return summaries


def domain_overview(runs: list[dict] | None = None) -> list[dict]:
    runs = runs if runs is not None else list_runs()
    by_domain: dict[str, list[dict]] = {d: [] for d in DOMAINS}
    for run in runs:
        domain = run.get("domain")
        if domain in by_domain:
            by_domain[domain].append(run)
    cards = []
    for domain in DOMAINS:
        items = by_domain[domain]
        latest = items[0] if items else None
        cards.append({
            "domain": domain,
            "n_runs": len(items),
            "latest": latest["name"] if latest else None,
            "placebo": latest["placebo"] if latest else None,
            "skill": latest["skill"] if latest else None,
            "net_delta": latest["net_delta"] if latest else None,
            "n_tasks": latest["n_tasks"] if latest else None,
            "total_cost": latest["total_cost"] if latest else None,
            "status": (
                "no_run" if not latest
                else "comparison" if latest.get("skill") is not None and latest.get("placebo") is not None
                else "no_placebo"
            ),
        })
    return cards


def load_experiments() -> list[dict]:
    directory = REPO_ROOT / "research" / "experiments"
    items: dict[str, dict] = {}
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            data = _load_json(path)
            if data and data.get("experiment_id"):
                items[str(data["experiment_id"])] = data
    for row in _load_jsonl(directory / "experiment_log.jsonl"):
        eid = row.get("experiment_id")
        if eid:
            items.setdefault(str(eid), row)
    runs = {r["run_dir"]: r for r in list_runs()}
    runs_by_name = {r["name"]: r for r in list_runs()}
    out = []
    for exp in items.values():
        run_dir = str(exp.get("run_dir") or "")
        name = Path(run_dir).name if run_dir else None
        run = runs.get(run_dir) or (runs_by_name.get(name) if name else None)
        out.append({
            **{k: exp.get(k) for k in (
                "experiment_id", "domain", "date", "hypothesis", "skill_version",
                "task_set", "arms", "concurrency", "run_dir", "notes", "conclusion",
            )},
            "score": (run or {}).get("skill"),
            "net_delta": (run or {}).get("net_delta"),
            "total_cost": (run or {}).get("total_cost"),
            "n_tasks": (run or {}).get("n_tasks"),
            "linked_run": (run or {}).get("name"),
        })
    out.sort(key=lambda e: str(e.get("date") or ""), reverse=True)
    return out


def load_dataset() -> dict:
    audit = _load_json_any(REPO_ROOT / "research" / "data" / "audit_summary.json")
    manifest = _load_json(REPO_ROOT / "research" / "sampling" / "task_sets" / "manifest_v1.json")
    domains = []
    audit_rows = audit if isinstance(audit, list) else []
    splits = {
        row.get("domain"): row
        for row in ((manifest or {}).get("domains") or [])
        if isinstance(row, dict)
    }
    seen = set()
    for row in audit_rows:
        domain = row.get("domain")
        split = splits.get(domain) or {}
        seen.add(domain)
        domains.append({
            "domain": domain,
            "benchmark": row.get("benchmark"),
            "n_train": row.get("n_official_train") or row.get("n_local_tasks"),
            "n_flagged": row.get("n_flagged"),
            "n_duplicate_groups": row.get("n_exact_duplicate_groups"),
            "flag_counts": row.get("flag_counts") or {},
            "stratum_counts": row.get("stratum_counts") or {},
            "n_dev": split.get("n_dev"),
            "n_validation": split.get("n_validation"),
            "split_strata": {
                k: {"dev": v.get("dev"), "validation": v.get("validation")}
                for k, v in (split.get("strata") or {}).items()
                if isinstance(v, dict)
            },
        })
    for domain, split in splits.items():
        if domain in seen:
            continue
        domains.append({
            "domain": domain,
            "n_train": split.get("n_pool"),
            "n_dev": split.get("n_dev"),
            "n_validation": split.get("n_validation"),
            "split_strata": split.get("strata") or {},
        })
    return {
        "domains": domains,
        "task_set": {
            "version": (manifest or {}).get("version"),
            "seed": (manifest or {}).get("seed"),
            "source_pool": (manifest or {}).get("source_pool"),
            "selection": (manifest or {}).get("selection"),
        } if manifest else None,
    }


def overview() -> dict:
    runs = list_runs()
    return {
        "runs": runs,
        "domains": domain_overview(runs),
        "experiments": load_experiments(),
        "dataset": load_dataset(),
    }
