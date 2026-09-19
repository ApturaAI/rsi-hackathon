#!/usr/bin/env python3
"""Build deterministic research-dev / validation task sets from the task index."""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.lib import (  # noqa: E402
    DOMAINS,
    REPO_ROOT,
    TASK_SET_SEED,
    TASK_SET_SIZES,
    TASK_SET_VERSION,
    allocate,
    read_jsonl,
    write_json,
)

OUT_DIR = REPO_ROOT / "research" / "sampling" / "task_sets"


def load_pool(index_path: Path, domain: str) -> list[dict]:
    if not index_path.is_file():
        raise FileNotFoundError(
            f"missing {index_path} — run research/audit/audit_dataset.py first"
        )
    rows = [row for row in read_jsonl(index_path) if row.get("domain") == domain]
    pool = [
        row for row in rows
        if row.get("in_official_train_pool") and row.get("task_name")
    ]
    if not pool:
        raise ValueError(f"no official-train tasks for {domain} in {index_path}")
    return pool


def split_domain(rows: list[dict], n_dev: int, n_val: int, seed: int, domain: str) -> dict:
    by_stratum: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        name = str(row["task_name"])
        stratum = str(row.get("stratum") or "unknown")
        by_stratum[stratum].append(name)
    for names in by_stratum.values():
        names.sort()

    rng = random.Random(f"{seed}:{domain}:{TASK_SET_VERSION}")
    shuffled = {}
    for stratum in sorted(by_stratum):
        names = list(by_stratum[stratum])
        rng.shuffle(names)
        shuffled[stratum] = names

    sizes = {stratum: len(names) for stratum, names in shuffled.items()}
    sample_alloc = allocate(sizes, n_dev + n_val)
    dev_alloc = allocate(sample_alloc, n_dev)
    val_alloc = {k: sample_alloc[k] - dev_alloc[k] for k in sample_alloc}

    dev: list[str] = []
    val: list[str] = []
    unused: dict[str, int] = {}
    for stratum in sorted(shuffled):
        names = shuffled[stratum]
        n_d = dev_alloc[stratum]
        n_v = val_alloc[stratum]
        dev.extend(names[:n_d])
        val.extend(names[n_d:n_d + n_v])
        unused[stratum] = len(names) - n_d - n_v

    overlap = set(dev) & set(val)
    if overlap:
        raise RuntimeError(f"{domain} split leaked {sorted(overlap)[:5]}")
    return {
        "domain": domain,
        "seed": seed,
        "version": TASK_SET_VERSION,
        "n_pool": len(rows),
        "n_dev": len(dev),
        "n_validation": len(val),
        "requested": {"dev": n_dev, "validation": n_val},
        "strata": {
            stratum: {
                "pool": sizes[stratum],
                "dev": dev_alloc[stratum],
                "validation": val_alloc[stratum],
                "unused": unused[stratum],
            }
            for stratum in sorted(sizes)
        },
        "dev": sorted(dev),
        "validation": sorted(val),
    }


def write_name_file(path: Path, names: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{name}\n" for name in names), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default=str(REPO_ROOT / "research" / "data" / "task_index.jsonl"))
    parser.add_argument("--seed", type=int, default=TASK_SET_SEED)
    parser.add_argument("--version", default=TASK_SET_VERSION)
    parser.add_argument("--write", action="store_true", help="write task-set files")
    args = parser.parse_args(argv)

    index_path = Path(args.index)
    splits = []
    for domain in DOMAINS:
        n_dev, n_val = TASK_SET_SIZES[domain]
        pool = load_pool(index_path, domain)
        splits.append(split_domain(pool, n_dev, n_val, args.seed, domain))

    manifest = {
        "version": args.version,
        "seed": args.seed,
        "source_index": str(index_path),
        "source_pool": "official training split (dev_task_names only); organiser held-out names unused",
        "selection": (
            "Deterministic largest-remainder allocation within official metadata strata. "
            "Tasks are sorted by name, then shuffled with Random(f'{seed}:{domain}:{version}'). "
            "No answer, rubric, reference, or expected-action fields are read."
        ),
        "domains": splits,
        "stbench_eval_note": "Pass a task file with --tasks $(paste -sd, file.txt)",
    }

    print(f"seed={args.seed} version={args.version}")
    for split in splits:
        print(
            f"{split['domain']}: pool={split['n_pool']} "
            f"dev={split['n_dev']} val={split['n_validation']} "
            f"strata={ {k: v['dev'] + v['validation'] for k, v in split['strata'].items()} }"
        )

    if not args.write:
        print("dry run; pass --write to emit files")
        return 0

    out = OUT_DIR
    for split in splits:
        domain = split["domain"]
        write_name_file(out / f"{domain}_dev_{args.version}.txt", split["dev"])
        write_name_file(out / f"{domain}_validation_{args.version}.txt", split["validation"])
    write_json(out / f"manifest_{args.version}.json", manifest)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
