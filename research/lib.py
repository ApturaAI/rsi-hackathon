"""Shared helpers for local research scripts. No model or Docker calls."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent

DOMAINS = ("health", "qf", "tau3", "hle")

# Official training-split files. Only `dev_task_names` is a legal pool.
OFFICIAL_SPLITS: dict[str, Path] = {
    "health": REPO_ROOT / "dataset/hackathon/splits/healthbench/hb-hardbeh-s002.json",
    "qf": REPO_ROOT / "dataset/hackathon/splits/QuantitativeFinance-Bench/qf-medhard-strat-80-s005.json",
    "tau3": REPO_ROOT / "dataset/hackathon/splits/tau3-bench/tau3-banking-70-s001.json",
    "hle": REPO_ROOT / "dataset/hackathon/splits/hle/hle-stem517-s001.json",
}

SPLIT_IDS = {
    "health": "hb-hardbeh-s002",
    "qf": "qf-medhard-strat-80-s005",
    "tau3": "tau3-banking-70-s001",
    "hle": "hle-stem517-s001",
}

# Documented quality-flag thresholds (character counts).
SHORT_INSTRUCTION = 40
SHORT_PROMPT = 20
EXTREME_PROMPT = {
    "health": 4000,
    "qf": 14000,
    "tau3": 12000,
    "hle": 8000,
}

INFRA_STATUSES = frozenset({"infra_error", "timeout", "budget_exhausted"})
LEARNER_STATUSES = frozenset({"ok", "invalid_output"})

TASK_SET_SEED = 20260919
TASK_SET_VERSION = "v1"
TASK_SET_SIZES = {
    "health": (12, 12),
    "qf": (8, 8),
    "tau3": (8, 8),
    "hle": (12, 12),
}


def domain_cfg(name: str):
    """Return the pinned DomainCfg from hackathon.toml."""
    from skilltrainbench.config import load_config

    if name not in DOMAINS:
        raise ValueError(f"unknown domain {name!r}; have {list(DOMAINS)}")
    return load_config().domain(name)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as error:
            rows.append({"_parser_error": f"malformed jsonl line {i}: {error}"})
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            rows.append({"_parser_error": f"line {i} is {type(obj).__name__}, not object"})
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def official_train_names(domain: str) -> set[str]:
    """Training-task folder names only. Held-out names are never returned."""
    path = OFFICIAL_SPLITS[domain]
    if not path.is_file():
        raise FileNotFoundError(f"official split missing: {path} — run `stbench data pull`")
    data = read_json(path)
    names = data.get("dev_task_names")
    if not isinstance(names, list):
        raise ValueError(f"{path} has no dev_task_names list")
    return {str(name) for name in names}


def classify_outcome(
    *,
    status: str | None,
    verifier_status: str | None,
    trial_found: bool,
    parse_errors: list[str],
) -> str:
    """Separate infrastructure / grader / parser issues from learner outcomes."""
    if parse_errors:
        return "parser_failure"
    if status in INFRA_STATUSES or verifier_status == "budget_exhausted":
        return "infra_failure"
    if not trial_found:
        return "infra_failure" if status not in LEARNER_STATUSES else "parser_failure"
    if verifier_status == "invalidated":
        return "grader_failure"
    if status in LEARNER_STATUSES or status is None:
        return "learner_outcome"
    return "parser_failure"


def allocate(counts: dict[str, int], n: int) -> dict[str, int]:
    """Largest-remainder allocation, never exceeding available counts."""
    keys = sorted(counts)
    total = sum(counts[k] for k in keys)
    if total <= 0 or n <= 0:
        return {k: 0 for k in keys}
    n = min(n, total)
    raw = {k: n * counts[k] / total for k in keys}
    taken = {k: min(counts[k], int(raw[k])) for k in keys}
    leftover = n - sum(taken.values())
    remainders = sorted((raw[k] - taken[k], k) for k in keys)
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for _, key in remainders:
        if leftover <= 0:
            break
        if taken[key] < counts[key]:
            taken[key] += 1
            leftover -= 1
    if leftover:
        for key in keys:
            while leftover and taken[key] < counts[key]:
                taken[key] += 1
                leftover -= 1
    return taken


def normalize_qf_difficulty(raw: str | None) -> str:
    if raw in {"hard", "very_hard"}:
        return "hard"
    if raw in {"medium", "medium-hard"}:
        return "medium"
    if raw in {"easy"}:
        return "easy"
    return "unknown"


def health_theme(tags: Iterable[str]) -> str | None:
    themes = [tag.removeprefix("theme:") for tag in tags if tag.startswith("theme:")]
    return themes[0] if themes else None


def counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}
