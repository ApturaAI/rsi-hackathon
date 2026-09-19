#!/usr/bin/env python3
"""Inventory training tasks and flag data-quality issues. Local files only."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.lib import (  # noqa: E402
    DOMAINS,
    EXTREME_PROMPT,
    REPO_ROOT,
    SHORT_INSTRUCTION,
    SHORT_PROMPT,
    SPLIT_IDS,
    domain_cfg,
    health_theme,
    normalize_qf_difficulty,
    official_train_names,
    sha256_bytes,
    sha256_text,
    write_json,
    write_jsonl,
)
from skilltrainbench.tasks import REQUIRED_FILES, read_task_toml  # noqa: E402


def _read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="replace"), "unusual_encoding"
        except OSError as error:
            return None, f"unreadable:{error}"
    except OSError as error:
        return None, f"unreadable:{error}"


def _file_hash(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError:
        return None


def _safe_json(path: Path) -> tuple[dict | list | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, f"malformed_json:{path.name}:{error}"
    return value, None


def _task_toml(task_dir: Path) -> tuple[dict | None, list[str]]:
    flags: list[str] = []
    try:
        data = read_task_toml(task_dir)
    except RuntimeError:
        flags.append("malformed_task_toml")
        return None, flags
    return data, flags


def _audit_health(task_dir: Path, flags: list[str]) -> dict:
    extra: dict = {}
    example, error = _safe_json(task_dir / "tests" / "example.json")
    if error:
        flags.append(error)
        return extra
    if not isinstance(example, dict):
        flags.append("malformed_example_json")
        return extra
    tags = [str(t) for t in (example.get("example_tags") or []) if isinstance(t, str)]
    prompt = example.get("prompt") if isinstance(example.get("prompt"), list) else []
    messages = [m for m in prompt if isinstance(m, dict)]
    prompt_text = "\n".join(str(m.get("content") or "") for m in messages)
    rubrics = example.get("rubrics") if isinstance(example.get("rubrics"), list) else []
    theme = health_theme(tags)
    extra.update({
        "example_tags": tags,
        "theme": theme,
        "stratum": theme or "unknown",
        "conversation_turns": len(messages),
        "prompt_length": len(prompt_text),
        "n_rubrics": len(rubrics),
        "prompt_sha256": sha256_text(prompt_text),
    })
    if not messages:
        flags.append("empty_conversation")
    elif len(prompt_text) < SHORT_PROMPT:
        flags.append("short_prompt")
    if len(prompt_text) > EXTREME_PROMPT["health"]:
        flags.append("extreme_prompt_length")
    if theme is None:
        flags.append("missing_theme")
    metadata = example.get("metadata") if isinstance(example.get("metadata"), dict) else {}
    extra["variant"] = metadata.get("variant")
    extra["prompt_id"] = metadata.get("prompt_id")
    return extra


def _audit_qf(task_dir: Path, toml_data: dict | None, flags: list[str]) -> dict:
    metadata = (toml_data or {}).get("metadata") if isinstance((toml_data or {}).get("metadata"), dict) else {}
    difficulty = metadata.get("difficulty") if isinstance(metadata.get("difficulty"), str) else None
    category = metadata.get("category") if isinstance(metadata.get("category"), str) else None
    tags = [str(t) for t in (metadata.get("tags") or []) if isinstance(t, str)]
    if difficulty is None:
        flags.append("missing_difficulty")
    return {
        "difficulty": difficulty,
        "stratum": normalize_qf_difficulty(difficulty),
        "category": category,
        "qf_tags": tags,
    }


def _audit_tau3(task_dir: Path, flags: list[str]) -> dict:
    extra: dict = {}
    cfg, error = _safe_json(task_dir / "tests" / "config.json")
    if error:
        flags.append(error)
        return extra
    if not isinstance(cfg, dict):
        flags.append("malformed_config_json")
        return extra
    task = cfg.get("task") if isinstance(cfg.get("task"), dict) else {}
    scenario = task.get("user_scenario") if isinstance(task.get("user_scenario"), dict) else {}
    instructions = scenario.get("instructions")
    prompt_length = len(instructions) if isinstance(instructions, str) else None
    if isinstance(instructions, str) and not instructions.strip():
        flags.append("empty_user_scenario")
    # Hash the simulated-user instructions, never expected_actions / evaluation_criteria.
    if isinstance(instructions, str) and instructions.strip():
        prompt_hash = sha256_text(instructions)
    else:
        prompt_hash = sha256_text(
            f"{cfg.get('domain')}|{cfg.get('source_task_id')}|{cfg.get('retrieval_variant')}"
        )
    extra.update({
        "tau3_domain": cfg.get("domain"),
        "source_task_id": cfg.get("source_task_id"),
        "retrieval_variant": cfg.get("retrieval_variant"),
        "reward_basis": list(cfg.get("reward_basis") or []) if isinstance(cfg.get("reward_basis"), list) else [],
        "n_expected_actions": len(cfg.get("expected_actions") or []) if isinstance(cfg.get("expected_actions"), list) else None,
        "n_required_documents": len(task.get("required_documents") or []) if isinstance(task.get("required_documents"), list) else None,
        "prompt_length": prompt_length,
        "prompt_sha256": prompt_hash,
        "stratum": str(cfg.get("domain") or "banking_knowledge"),
    })
    return extra


def _audit_hle(task_dir: Path, flags: list[str]) -> dict:
    extra: dict = {}
    meta, error = _safe_json(task_dir / "tests" / "metadata.json")
    if error:
        flags.append(error)
        meta = None
    if isinstance(meta, dict):
        extra.update({
            "hle_id": meta.get("id"),
            "category": meta.get("category"),
            "raw_subject": meta.get("raw_subject"),
            "answer_type": meta.get("answer_type"),
            "has_image": bool(meta.get("has_image")),
            "stratum": meta.get("category") or "unknown",
        })
        if extra["stratum"] == "unknown":
            flags.append("missing_category")
    question = task_dir / "tests" / "question.txt"
    text, qflag = _read_text(question) if question.is_file() else (None, "missing_question")
    if qflag == "unusual_encoding":
        flags.append("unusual_encoding")
    elif qflag == "missing_question":
        flags.append("missing_question")
    if text is not None:
        extra["prompt_length"] = len(text)
        extra["prompt_sha256"] = sha256_text(text)
        if not text.strip():
            flags.append("empty_prompt")
        elif len(text) < SHORT_PROMPT:
            flags.append("short_prompt")
        if len(text) > EXTREME_PROMPT["hle"]:
            flags.append("extreme_prompt_length")
    return extra


def audit_task(domain: str, benchmark: str, task_dir: Path, train_names: set[str]) -> dict:
    flags: list[str] = []
    required = REQUIRED_FILES[benchmark]
    missing = [rel for rel in required if not (task_dir / rel).is_file()]
    if missing:
        flags.append("missing_required_files")

    toml_data, toml_flags = _task_toml(task_dir)
    flags.extend(toml_flags)
    instruction, instr_flag = _read_text(task_dir / "instruction.md") if (task_dir / "instruction.md").is_file() else (None, "missing_instruction")
    if instr_flag == "unusual_encoding":
        flags.append("unusual_encoding")
    elif instr_flag == "missing_instruction":
        flags.append("missing_instruction")
    instruction_length = len(instruction) if instruction is not None else None
    if instruction is not None and not instruction.strip():
        flags.append("empty_instruction")
    elif instruction is not None and domain != "hle" and len(instruction) < SHORT_INSTRUCTION:
        flags.append("short_instruction")

    name = task_dir.name
    in_official = name in train_names
    if not in_official:
        flags.append("not_in_official_train_pool")

    extra: dict = {}
    if domain == "health":
        extra = _audit_health(task_dir, flags)
    elif domain == "qf":
        extra = _audit_qf(task_dir, toml_data, flags)
        extra["prompt_length"] = instruction_length
        if instruction_length and instruction_length > EXTREME_PROMPT["qf"]:
            flags.append("extreme_prompt_length")
    elif domain == "tau3":
        extra = _audit_tau3(task_dir, flags)
        if extra.get("prompt_length") is None:
            extra["prompt_length"] = instruction_length
    elif domain == "hle":
        extra = _audit_hle(task_dir, flags)

    content_hash = extra.get("prompt_sha256") or (
        sha256_text(instruction) if instruction else _file_hash(task_dir / "instruction.md")
    )
    metadata = (toml_data or {}).get("metadata") if isinstance((toml_data or {}).get("metadata"), dict) else {}
    timeout = None
    for section in ("agent", "verifier"):
        block = (toml_data or {}).get(section)
        if isinstance(block, dict) and isinstance(block.get("timeout_sec"), (int, float)):
            timeout = max(timeout or 0, float(block["timeout_sec"]))

    return {
        "task_name": name,
        "task_id": f"{benchmark}-train-{name}",
        "domain": domain,
        "benchmark": benchmark,
        "in_official_train_pool": in_official,
        "official_split_id": None,  # filled by caller
        "required_files_ok": not missing,
        "missing_files": missing,
        "instruction_length": instruction_length,
        "instruction_sha256": sha256_text(instruction) if instruction is not None else None,
        "content_sha256": content_hash,
        "timeout_sec": timeout,
        "task_toml_variant": metadata.get("variant") if domain == "health" else None,
        "data_quality_flags": sorted(set(flags)),
        **extra,
    }


def iter_task_dirs(dataset_dir: Path) -> list[Path]:
    if not dataset_dir.is_dir():
        return []
    return sorted(
        p for p in dataset_dir.iterdir()
        if p.is_dir() and not p.is_symlink()
    )


def audit_domain(domain: str) -> tuple[list[dict], dict]:
    cfg = domain_cfg(domain)
    train_names = official_train_names(domain)
    rows = [
        audit_task(domain, cfg.benchmark, task_dir, train_names)
        for task_dir in iter_task_dirs(cfg.dataset_dir)
    ]
    for row in rows:
        row["official_split_id"] = SPLIT_IDS[domain]
    by_hash: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        digest = row.get("content_sha256")
        if digest:
            by_hash[digest].append(row["task_name"])
    duplicates = {digest: names for digest, names in by_hash.items() if len(names) > 1}
    for row in rows:
        digest = row.get("content_sha256")
        if digest in duplicates:
            row["data_quality_flags"] = sorted(set(row["data_quality_flags"] + ["exact_duplicate"]))
            row["duplicate_of"] = [n for n in duplicates[digest] if n != row["task_name"]]
        else:
            row["duplicate_of"] = []
    local_names = {row["task_name"] for row in rows}
    summary = {
        "domain": domain,
        "benchmark": cfg.benchmark,
        "n_local_tasks": len(rows),
        "n_official_train": len(train_names),
        "n_missing_locally": len(train_names - local_names),
        "n_not_in_official_train": sum(1 for row in rows if not row["in_official_train_pool"]),
        "n_flagged": sum(1 for row in rows if row["data_quality_flags"]),
        "flag_counts": dict(sorted(Counter(flag for row in rows for flag in row["data_quality_flags"]).items())),
        "stratum_counts": dict(sorted(Counter(row.get("stratum") or "unknown" for row in rows).items())),
        "n_exact_duplicate_groups": len(duplicates),
        "missing_local_official_train_count": len(train_names - local_names),
    }
    return rows, summary


def format_report(summaries: list[dict], rows: list[dict]) -> str:
    lines = ["dataset audit (flags only; no repairs, no hidden answers)", ""]
    for summary in summaries:
        lines.append(
            f"{summary['domain']}: {summary['n_local_tasks']} local / "
            f"{summary['n_official_train']} official-train · "
            f"flagged {summary['n_flagged']} · "
            f"duplicate groups {summary['n_exact_duplicate_groups']}"
        )
        lines.append(f"  strata: {summary['stratum_counts']}")
        if summary["flag_counts"]:
            lines.append(f"  flags: {summary['flag_counts']}")
        if summary["n_missing_locally"]:
            lines.append(f"  official-train missing locally: {summary['n_missing_locally']}")
        lines.append("")
    flagged = [row for row in rows if row["data_quality_flags"]]
    if flagged:
        lines.append("flagged tasks (name · flags):")
        for row in flagged:
            lines.append(f"  {row['domain']}/{row['task_name']}  {row['data_quality_flags']}")
    else:
        lines.append("no quality flags")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", action="append", choices=DOMAINS, dest="domains")
    parser.add_argument("--all-domains", action="store_true", help="audit health, qf, tau3, hle")
    parser.add_argument(
        "--out-index",
        default=str(REPO_ROOT / "research" / "data" / "task_index.jsonl"),
    )
    parser.add_argument(
        "--out-report",
        default=str(REPO_ROOT / "research" / "reports" / "dataset_audit.txt"),
    )
    args = parser.parse_args(argv)
    domains = list(args.domains or [])
    if args.all_domains or not domains:
        domains = list(DOMAINS)

    all_rows: list[dict] = []
    summaries: list[dict] = []
    for domain in domains:
        rows, summary = audit_domain(domain)
        all_rows.extend(rows)
        summaries.append(summary)

    index_path = Path(args.out_index)
    report_path = Path(args.out_report)
    write_jsonl(index_path, all_rows)
    write_json(REPO_ROOT / "research" / "data" / "audit_summary.json", summaries)
    text = format_report(summaries, all_rows)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"wrote {index_path}")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
