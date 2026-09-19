"""Paired scoring: per-arm rates, the placebo-adjusted delta, and a task-clustered
bootstrap CI once there are at least 12 tasks."""

from __future__ import annotations

import random
from dataclasses import dataclass

MIN_CI_TASKS = 12


@dataclass(frozen=True)
class Pair:
    task_id: str
    seed: int
    baseline: float | None = None  # learner score WITHOUT any skill (None = arm not run)
    skill: float | None = None  # learner score WITH the curator's skill
    placebo: float | None = None  # learner score WITH a generic content-free skill
    domain: str | None = None  # task domain, for the per-domain breakdown (None -> "unknown")
    # Arms that DID run but produced no score because the judge refused to grade
    # them (plan Task 7 invalidation). Without this, such an arm is
    # indistinguishable from "arm not run" — both are None — and the balanced-arm
    # guard below cannot tell a structural bug from a legitimate ungraded
    # response. Empty for deterministic domains, which never invalidate.
    invalidated: frozenset[str] = frozenset()


def _domain_block(dp: list["Pair"]) -> dict:
    """Per-domain rates over a subset of pairs (same math as the headline, scoped to one
    domain). Rates are None for arms that didn't run; net_delta needs a control
    (placebo when present, else baseline) and is None without one."""
    has_plac = any(p.placebo is not None for p in dp)
    base = _rate_or_none(dp, "baseline")
    skill = _rate(dp, "skill")
    plac = _rate_or_none(dp, "placebo") if has_plac else None
    if plac is not None:
        net = skill - plac
    elif base is not None:
        net = skill - base
    else:
        net = None
    return {
        "baseline_rate": round(base, 4) if base is not None else None,
        "placebo_rate": round(plac, 4) if plac is not None else None,
        "skill_rate": round(skill, 4),
        "net_delta": round(net, 4) if net is not None else None,
        "n_tasks": len({p.task_id for p in dp}),
    }


def _rate(pairs, field) -> float:
    vals = [v for v in (getattr(p, field) for p in pairs) if v is not None]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def _rate_or_none(pairs, field) -> float | None:
    """Like _rate, but None when the arm never ran (skill-only evals have no
    baseline rate — reporting 0.0 would be a lie)."""
    vals = [v for v in (getattr(p, field) for p in pairs) if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _cluster_bootstrap_ci(pairs, task_ids, control, iters=1000, seed=0):
    """CI on the SCORED delta = skill - control ('placebo' if present else 'baseline')."""
    rng = random.Random(seed)
    by_task = {tid: [p for p in pairs if p.task_id == tid] for tid in task_ids}
    deltas = []
    k = len(task_ids)
    for _ in range(iters):
        ps = [p for tid in (rng.choice(task_ids) for _ in range(k)) for p in by_task[tid]]
        deltas.append(_rate(ps, "skill") - _rate(ps, control))
    deltas.sort()
    lo = deltas[int(0.025 * len(deltas))]
    hi = deltas[min(len(deltas) - 1, int(0.975 * len(deltas)))]
    return [round(lo, 4), round(hi, 4)]


def _validate_balanced_arms(pairs: list[Pair]) -> None:
    active = [
        field
        for field in ("baseline", "placebo", "skill")
        if any(getattr(pair, field) is not None for pair in pairs)
    ]
    missing = {
        field: [pair.task_id for pair in pairs if getattr(pair, field) is None]
        for field in active
        if any(getattr(pair, field) is None for pair in pairs)
    }
    if missing:
        detail = ", ".join(f"{field}={ids}" for field, ids in missing.items())
        raise ValueError(f"unbalanced arms: {detail}")


def _clip_official(value: float | None) -> float | None:
    return min(1.0, max(0.0, value)) if value is not None else None


def summarize(pairs: list[Pair], min_ci_tasks: int = MIN_CI_TASKS, seed: int = 0) -> dict:
    if not pairs:
        return {"baseline_rate": None, "placebo_rate": None, "skill_rate": None, "delta": None,
                "net_delta": None, "n_pairs": 0, "n_tasks": 0, "ci95": None, "note": "no_pairs",
                "arms": [], "control": None, "per_task": [], "by_domain": {},
                "n_invalidated_per_arm": {}}
    # A task is unusable for a PAIRED comparison when any arm it ran came back
    # ungraded (plan Task 7 judge invalidation), or when no arm graded at all.
    # Comparing the remaining arms would silently compute the delta over a
    # different task set per arm, which is exactly the bias the balance guard
    # exists to prevent — so these are excluded from the rates and reported as a
    # count instead. An arm that never RAN is a different thing entirely and
    # still reaches _validate_balanced_arms below as a structural error.
    def _unusable(pair: Pair) -> bool:
        if pair.invalidated:
            return True
        return pair.baseline is None and pair.placebo is None and pair.skill is None

    n_invalidated = sum(_unusable(p) for p in pairs)
    active_arms = {
        arm
        for pair in pairs
        for arm in ("baseline", "placebo", "skill")
        if getattr(pair, arm) is not None or arm in pair.invalidated
    }
    if any(
        pair.baseline is None
        and pair.placebo is None
        and pair.skill is None
        and not pair.invalidated
        for pair in pairs
    ):
        active_arms.update(("baseline", "placebo", "skill"))
    n_invalidated_per_arm = {
        arm: sum(
            arm in pair.invalidated
            or (
                not pair.invalidated
                and pair.baseline is None
                and pair.placebo is None
                and pair.skill is None
            )
            for pair in pairs
        )
        for arm in ("baseline", "placebo", "skill")
        if arm in active_arms
    }
    all_task_ids = sorted({p.task_id for p in pairs})
    pairs_all = pairs
    pairs = [p for p in pairs_all if not _unusable(p)]
    if not pairs:
        return {"baseline_rate": None, "placebo_rate": None, "skill_rate": None, "delta": None,
                "net_delta": None, "n_pairs": 0, "n_tasks": 0, "ci95": None,
                "note": "all_tasks_invalidated", "arms": [], "control": None,
                "per_task": [], "by_domain": {}, "n_invalidated_tasks": n_invalidated,
                "n_invalidated_per_arm": n_invalidated_per_arm}
    _validate_balanced_arms(pairs)
    n = len(pairs)
    task_ids = sorted({p.task_id for p in pairs})
    has_baseline = any(p.baseline is not None for p in pairs)
    baseline_rate = _rate_or_none(pairs, "baseline") if has_baseline else None
    skill_rate = _rate_or_none(pairs, "skill")
    has_placebo = any(p.placebo is not None for p in pairs)
    placebo_rate = _rate_or_none(pairs, "placebo") if has_placebo else None
    arms = [a for a, has in (("baseline", has_baseline), ("placebo", has_placebo),
                             ("skill", any(p.skill is not None for p in pairs))) if has]
    # control = what the delta is measured against (placebo-adjusted when present)
    control = "placebo" if has_placebo else ("baseline" if has_baseline else None)
    raw_delta = (skill_rate - baseline_rate) if (skill_rate is not None and baseline_rate is not None) else None
    # net_delta subtracts the placebo (generic-context) lift -> the rule-attributable delta
    net_delta = (skill_rate - placebo_rate) if (has_placebo and skill_rate is not None and placebo_rate is not None) else raw_delta
    # per_task covers EVERY task, including fully invalidated ones (all-None
    # arms) — it is the per-task record, not an aggregate input.
    per_task = [
        {"task_id": tid,
         "baseline": (sum(p.baseline for p in pairs_all if p.task_id == tid and p.baseline is not None)
                      if any(p.baseline is not None for p in pairs_all if p.task_id == tid) else None),
         "placebo": (sum(p.placebo for p in pairs_all if p.task_id == tid and p.placebo is not None)
                     if any(p.placebo is not None for p in pairs_all if p.task_id == tid) else None),
         "skill": (sum(p.skill for p in pairs_all if p.task_id == tid and p.skill is not None)
                   if any(p.skill is not None for p in pairs_all if p.task_id == tid) else None)}
        for tid in all_task_ids
    ]
    if control is not None and len(task_ids) >= min_ci_tasks:
        ci = _cluster_bootstrap_ci(pairs, task_ids, control, seed=seed)
        note = None
    elif control is None:
        ci = None
        note = "skill_only_no_control"
    else:
        ci = None
        note = "pipeline_green_not_statistically_valid"
    # per-domain rollup (domain-less pairs bucket under "unknown"); headline fields above
    # are unchanged — this is a strictly additive breakdown.
    by_domain = {
        d: _domain_block([p for p in pairs if (p.domain or "unknown") == d])
        for d in sorted({(p.domain or "unknown") for p in pairs})
    }
    result = {
        "baseline_rate": round(baseline_rate, 4) if baseline_rate is not None else None,
        "placebo_rate": round(placebo_rate, 4) if placebo_rate is not None else None,
        "skill_rate": round(skill_rate, 4) if skill_rate is not None else None,
        "delta": round(raw_delta, 4) if raw_delta is not None else None,  # raw skill - baseline
        "net_delta": round(net_delta, 4) if net_delta is not None else None,  # skill - control; the SCORED delta
        "n_pairs": n,
        "n_tasks": len(task_ids),
        "n_invalidated_tasks": n_invalidated if n_invalidated else 0,
        "n_invalidated_per_arm": n_invalidated_per_arm,
        "ci95": ci,
        "note": note,
        "arms": arms,
        "control": control,
        "per_task": per_task,
        "by_domain": by_domain,
    }
    if any(pair.domain in {"healthbench", "healthbench-harbor"} for pair in pairs):
        result["healthbench_official_score"] = {
            "baseline": (
                round(_clip_official(baseline_rate), 4) if baseline_rate is not None else None
            ),
            "placebo": (
                round(_clip_official(placebo_rate), 4) if placebo_rate is not None else None
            ),
            "skill": round(_clip_official(skill_rate), 4) if skill_rate is not None else None,
        }
    return result
