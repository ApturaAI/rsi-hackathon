#!/usr/bin/env python3
"""Join a completed stbench run into a research table. Local files only."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.lib import (  # noqa: E402
    REPO_ROOT,
    classify_outcome,
    counter_to_dict,
    read_json,
    read_jsonl,
    write_json,
    write_jsonl,
)

SAFE_METRIC_PREFIXES = ("axis:", "theme:", "physician_agreed_category:", "overall_score")


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        value = read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, f"{path.name}: {error}"
    return value if isinstance(value, dict) else None, None


def _find_trial(run_dir: Path, task_id: str, trial_dir: str | None) -> Path | None:
    if trial_dir:
        path = Path(trial_dir)
        if path.is_dir():
            return path
        rel = run_dir / path.name
        if rel.is_dir():
            return rel
    jobs = run_dir / "harbor-jobs"
    if not jobs.is_dir():
        return None
    matches = sorted(p for p in jobs.iterdir() if p.is_dir() and p.name.startswith(task_id))
    if not matches:
        return None
    for job in matches:
        trials = sorted(c for c in job.iterdir() if c.is_dir() and (c / "result.json").is_file())
        if trials:
            return trials[0]
    return None


def _trajectory_stats(trial: Path) -> tuple[dict, list[str]]:
    errors: list[str] = []
    path = trial / "agent" / "trajectory.json"
    if not path.is_file():
        return {}, ["missing trajectory.json"]
    data, error = _load_json(path)
    if error or data is None:
        return {}, [error or "trajectory.json is not an object"]
    steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    tools: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        for call in step.get("tool_calls") or []:
            if isinstance(call, dict):
                name = call.get("function_name") or call.get("name")
                if name:
                    tools.append(str(name))
    metrics = data.get("final_metrics") if isinstance(data.get("final_metrics"), dict) else {}
    counts = Counter(tools)
    return {
        "n_steps": len(steps),
        "n_agent_steps": sum(
            1 for step in steps if isinstance(step, dict) and step.get("source") == "agent"
        ),
        "n_tool_calls": len(tools),
        "tool_counts": counter_to_dict(counts),
        "n_repeated_tools": sum(n - 1 for n in counts.values() if n > 1),
        "trajectory_prompt_tokens": metrics.get("total_prompt_tokens"),
        "trajectory_completion_tokens": metrics.get("total_completion_tokens"),
        "trajectory_cached_tokens": metrics.get("total_cached_tokens"),
    }, errors


def _safe_health_verifier(verdicts: dict, reward: dict | None) -> dict:
    metrics_in = verdicts.get("metrics") if isinstance(verdicts.get("metrics"), dict) else {}
    metrics = {
        key: value
        for key, value in metrics_in.items()
        if isinstance(key, str) and key.startswith(SAFE_METRIC_PREFIXES)
    }
    rubrics = verdicts.get("rubrics") if isinstance(verdicts.get("rubrics"), list) else []
    n_met = 0
    n_unmet = 0
    plus_avail = plus_met = minus_avail = minus_hit = 0
    tag_counts: Counter[str] = Counter()
    for item in rubrics:
        if not isinstance(item, dict):
            continue
        points = item.get("points")
        met = bool(item.get("criteria_met"))
        if met:
            n_met += 1
        else:
            n_unmet += 1
        if isinstance(points, (int, float)):
            if points >= 0:
                plus_avail += points
                if met:
                    plus_met += points
            else:
                minus_avail += points
                if met:
                    minus_hit += points
        for tag in item.get("tags") or []:
            if isinstance(tag, str) and tag.startswith(("axis:", "theme:", "level:")):
                tag_counts[tag] += 1
    out = {
        "metrics": metrics,
        "n_rubrics": len(rubrics),
        "n_criteria_met": n_met,
        "n_criteria_unmet": n_unmet,
        "positive_points_available": plus_avail,
        "positive_points_met": plus_met,
        "negative_points_available": minus_avail,
        "negative_points_triggered": minus_hit,
        "rubric_tag_counts": counter_to_dict(tag_counts),
    }
    if reward:
        for key in ("reward", "healthbench_raw_score", "rubric_positive_met", "rubric_negative_met"):
            if key in reward:
                out[key] = reward[key]
    return out


def _trial_fields(trial: Path | None) -> tuple[dict, list[str]]:
    if trial is None:
        return {}, ["trial directory not found"]
    errors: list[str] = []
    result, error = _load_json(trial / "result.json")
    if error:
        errors.append(error)
    result = result or {}
    exc = result.get("exception_info") if isinstance(result.get("exception_info"), dict) else None
    error_class = None
    if exc:
        error_class = str(exc.get("exception_type") or "harbor_exception")[:120]
    agent = result.get("agent_result") if isinstance(result.get("agent_result"), dict) else {}
    verifier_result = result.get("verifier_result") if isinstance(result.get("verifier_result"), dict) else {}
    rewards = verifier_result.get("rewards") if isinstance(verifier_result.get("rewards"), dict) else {}

    grading_status = None
    status_file = trial / "verifier" / "grading_status"
    if status_file.is_file():
        try:
            grading_status = status_file.read_text(encoding="utf-8").strip().lower() or None
        except OSError as status_error:
            errors.append(f"grading_status: {status_error}")

    # HealthBench writes reward.json / verdicts.json; other benchmarks do not.
    reward = verdicts = None
    if (trial / "verifier" / "reward.json").is_file():
        reward, reward_error = _load_json(trial / "verifier" / "reward.json")
        if reward_error:
            errors.append(reward_error)
    if (trial / "verifier" / "verdicts.json").is_file():
        verdicts, verdicts_error = _load_json(trial / "verifier" / "verdicts.json")
        if verdicts_error:
            errors.append(verdicts_error)
    if reward is None and (trial / "verifier" / "result.json").is_file():
        reward, reward_error = _load_json(trial / "verifier" / "result.json")
        if reward_error:
            errors.append(reward_error)

    traj, traj_errors = _trajectory_stats(trial)
    errors.extend(traj_errors)

    verifier: dict = {}
    if verdicts is not None:
        verifier = _safe_health_verifier(verdicts, reward)
    elif reward:
        verifier = {k: reward[k] for k in reward if k in {
            "reward", "healthbench_raw_score", "rubric_positive_met", "rubric_negative_met", "success",
        }}
    elif rewards:
        verifier = {k: rewards[k] for k in rewards if k != "details"}

    return {
        "trial_found": True,
        "error_class": error_class,
        "verifier_status": grading_status,
        "agent_prompt_tokens": agent.get("n_input_tokens"),
        "agent_completion_tokens": agent.get("n_output_tokens"),
        "agent_cached_tokens": agent.get("n_cache_tokens"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
        "verifier": verifier or None,
        **traj,
    }, errors


def parse_run(run_dir: Path) -> tuple[list[dict], dict]:
    eval_path = run_dir / "eval_result.json"
    if not eval_path.is_file():
        raise FileNotFoundError(f"missing {eval_path}")
    result, error = _load_json(eval_path)
    if error or result is None:
        raise ValueError(error or "eval_result.json is not an object")

    attempts_path = run_dir / "attempts.jsonl"
    attempts = read_jsonl(attempts_path) if attempts_path.is_file() else []
    if not attempts:
        for row in result.get("per_task") or []:
            if not isinstance(row, dict):
                continue
            for arm in ("baseline", "placebo", "skill"):
                if row.get(arm) is not None:
                    attempts.append({
                        "task_id": row.get("task_id"),
                        "task_name": row.get("task_name"),
                        "arm": arm,
                        "score": row.get(arm),
                    })

    parsed: list[dict] = []
    for raw in attempts:
        parse_errors = []
        if raw.get("_parser_error"):
            parse_errors.append(str(raw["_parser_error"]))
        task_id = str(raw.get("task_id") or "")
        trial = _find_trial(run_dir, task_id, raw.get("trial_dir"))
        trial_fields, trial_errors = _trial_fields(trial)
        parse_errors.extend(trial_errors)
        answer = raw.get("answer")
        answer_len = len(answer) if isinstance(answer, str) else None
        status = raw.get("status")
        outcome = classify_outcome(
            status=status if isinstance(status, str) else None,
            verifier_status=trial_fields.get("verifier_status"),
            trial_found=bool(trial_fields.get("trial_found")),
            parse_errors=[e for e in parse_errors if "missing trajectory" not in e],
        )
        # A missing trajectory is a gap, not an automatic parser failure if result.json exists.
        if trial_fields.get("trial_found") and outcome == "parser_failure":
            serious = [e for e in parse_errors if not e.startswith("missing trajectory")]
            if not serious:
                outcome = classify_outcome(
                    status=status if isinstance(status, str) else None,
                    verifier_status=trial_fields.get("verifier_status"),
                    trial_found=True,
                    parse_errors=[],
                )
        row = {
            "run_dir": str(run_dir),
            "domain": result.get("domain"),
            "benchmark": result.get("benchmark"),
            "task_id": task_id or None,
            "task_name": raw.get("task_name"),
            "arm": raw.get("arm"),
            "score": raw.get("score"),
            "passed": raw.get("passed"),
            "status": status,
            "error_class": trial_fields.get("error_class"),
            "outcome_class": outcome,
            "answer_length": answer_len,
            "trial_dir": str(trial) if trial else raw.get("trial_dir"),
            "parse_errors": parse_errors,
            **{k: v for k, v in trial_fields.items() if k != "trial_found"},
        }
        parsed.append(row)

    summary = {
        "run_dir": str(run_dir),
        "domain": result.get("domain"),
        "benchmark": result.get("benchmark"),
        "learner": result.get("learner"),
        "skill_dir": result.get("skill_dir"),
        "arms": result.get("arms"),
        "tasks": result.get("tasks"),
        "official_summary": result.get("summary"),
        "learner_usage": result.get("learner_usage"),
        "learner_cost": result.get("learner_cost"),
        "grader_usage": result.get("grader_usage"),
        "grader_cost": result.get("grader_cost"),
        "n_attempts": len(parsed),
        "outcome_counts": counter_to_dict(Counter(r["outcome_class"] for r in parsed)),
        "arm_counts": counter_to_dict(Counter(str(r.get("arm")) for r in parsed)),
        "mean_score_by_arm": _mean_by_arm(parsed),
        "note": (
            "Local research parse of a completed run. Scores are copied from the official "
            "harness; this file does not rescore. Health verifier fields are axis/theme/"
            "point totals only — criterion text is omitted."
        ),
    }
    return parsed, summary


def _mean_by_arm(rows: list[dict]) -> dict[str, float | None]:
    buckets: dict[str, list[float]] = {}
    for row in rows:
        if row["outcome_class"] != "learner_outcome":
            continue
        if not isinstance(row.get("score"), (int, float)):
            continue
        buckets.setdefault(str(row.get("arm")), []).append(float(row["score"]))
    return {
        arm: round(sum(vals) / len(vals), 4) if vals else None
        for arm, vals in sorted(buckets.items())
    }


def format_summary(summary: dict, rows: list[dict]) -> str:
    official = summary.get("official_summary") or {}
    lines = [
        f"run: {summary['run_dir']}",
        f"domain: {summary.get('domain')} ({summary.get('benchmark')})",
        f"arms: {', '.join(summary.get('arms') or [])}",
        f"tasks: {len(summary.get('tasks') or [])} · attempts: {summary.get('n_attempts')}",
        f"official baseline_rate: {official.get('baseline_rate')}",
        f"official note: {official.get('note')}",
        f"outcome_counts: {summary.get('outcome_counts')}",
        f"mean_score_by_arm (learner_outcome only): {summary.get('mean_score_by_arm')}",
    ]
    usage = summary.get("learner_usage") or {}
    cost = summary.get("learner_cost") or {}
    gcost = summary.get("grader_cost") or {}
    lines.append(
        f"learner tokens: {usage.get('total_tokens')} · "
        f"learner ${cost.get('estimated_usd')} · grader ${gcost.get('estimated_usd')}"
    )
    lines.append("")
    lines.append("per-attempt:")
    for row in rows:
        theme = None
        metrics = (row.get("verifier") or {}).get("metrics") or {}
        for key in metrics:
            if key.startswith("theme:"):
                theme = key.split(":", 1)[1]
                break
        extra = f" theme={theme}" if theme else ""
        lines.append(
            f"  {row.get('arm'):<9} {row.get('score')!s:<8} {row.get('outcome_class'):<16} "
            f"ans={row.get('answer_length')} steps={row.get('n_steps')} "
            f"tools={row.get('n_tool_calls')}{extra}  {row.get('task_name')}"
        )
    lines.append("")
    lines.append(summary["note"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="path to a completed stbench run directory")
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: research/reports/<run-name>)",
    )
    args = parser.parse_args(argv)
    run_dir = Path(args.run).expanduser()
    if not run_dir.is_absolute():
        run_dir = (REPO_ROOT / run_dir).resolve()
    out = Path(args.out).expanduser() if args.out else REPO_ROOT / "research" / "reports" / run_dir.name
    if not out.is_absolute():
        out = (REPO_ROOT / out).resolve()

    rows, summary = parse_run(run_dir)
    write_jsonl(out / "attempts.jsonl", rows)
    write_json(out / "summary.json", summary)
    text = format_summary(summary, rows)
    (out / "summary.txt").write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"wrote {out / 'attempts.jsonl'}")
    print(f"wrote {out / 'summary.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
