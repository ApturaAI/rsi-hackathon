"""stbench CLI for the skill-writing hackathon."""

from __future__ import annotations

import argparse
import asyncio
import json
import os


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="stbench")
    sub = ap.add_subparsers(dest="cmd")
    dp = sub.add_parser("data", help="download the hackathon training tasks")
    dp_sub = dp.add_subparsers(dest="data_cmd")
    pull = dp_sub.add_parser("pull", help="download the training tasks from Hugging Face")
    pull.add_argument("--config", default=None)
    tl = sub.add_parser("tasks", help="list the training task names of a domain")
    tl.add_argument("--domain", required=True)
    tl.add_argument("--config", default=None)
    ev = sub.add_parser("eval", help="evaluate a skill folder with the pinned hackathon learner (local Docker)")
    ev.add_argument("--domain", required=True, help="domain from hackathon.toml (qf, health, tau3, hle)")
    ev.add_argument("--skill", default=None, help="skill folder (contains SKILL.md)")
    ev.add_argument("--arms", default="baseline,skill", help="comma list from baseline,placebo,skill")
    ev.add_argument("--tasks", default="", help="comma-separated task names (default: all training tasks)")
    ev.add_argument("--limit", type=int, default=None, help="evaluate only the first N selected tasks")
    ev.add_argument("--concurrency", type=int, default=None,
                    help="parallel task containers (default: hackathon.toml; lower it on a laptop for qf/tau3)")
    ev.add_argument("--out", required=True)
    ev.add_argument("--config", default=None, help="hackathon config (default: repo-root hackathon.toml)")
    ck = sub.add_parser("check-skill", help="static submission checks for a skill folder")
    ck.add_argument("skill")
    ck.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    if args.cmd is None:
        ap.print_help()
        return 1
    return _run(args)


def _run(args) -> int:
    from dotenv import load_dotenv

    from . import config, evaluate

    load_dotenv(config.REPO_ROOT / ".env")
    try:
        hcfg = config.load_config(args.config)
    except (OSError, KeyError, ValueError) as e:
        print(f"cannot load hackathon config: {e}")
        return 2
    try:
        if args.cmd == "check-skill":
            res = config.check_skill(args.skill, hcfg)
            print(json.dumps(res, indent=2))
            return 0 if res["ok"] else 1
        if args.cmd == "tasks":
            print("\n".join(config.task_names(hcfg.domain(args.domain))))
            return 0
        if args.cmd == "data":
            if args.data_cmd != "pull":
                print("usage: stbench data pull")
                return 2
            root = config.pull_data(hcfg, token=os.environ.get("HF_TOKEN"))
            for name, domain in hcfg.domains.items():
                if domain.dataset_dir.is_dir():
                    print(f"{name}: {len(config.task_names(domain))} tasks in {domain.dataset_dir}")
                else:
                    print(f"{name}: no tasks in the download ({domain.dataset_dir} missing)")
            print(f"data in {root}")
            return 0
    except ValueError as e:
        print(e)
        return 2

    base = os.environ.get("STBENCH_UPSTREAM_BASE_URL") or hcfg.upstream_base_url
    key = os.environ.get("STBENCH_UPSTREAM_KEY") or os.environ.get(hcfg.upstream_key_env)
    if not key:
        print(f"set {hcfg.upstream_key_env} in .env — this run spends provider credits")
        return 2
    rosetta_warning = _apple_silicon_rosetta_warning()
    if rosetta_warning:
        print(rosetta_warning)
    from . import harbor

    if not harbor.egress_allowlist_supported():
        print("WARNING: this Docker daemon's kernel cannot enforce network allowlists (Docker Desktop lacks "
              "CONFIG_NFT_FIB_INET), so task containers run with public egress here. Scored runs on the "
              "organizers' Linux hosts restrict the learner to the gateway; do not rely on internet access.")
    if args.skill:
        check = config.check_skill(args.skill, hcfg)
        if not check["ok"]:
            print(json.dumps(check, indent=2))
            return 1
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    task_ids = [t.strip() for t in args.tasks.split(",") if t.strip()] or None
    try:
        res = asyncio.run(evaluate.run_eval(
            hcfg, args.domain, skill_dir=args.skill, out=args.out, arms=arms,
            task_ids=task_ids, limit=args.limit, upstream_base_url=base, upstream_key=key,
            concurrency=args.concurrency,
        ))
    except (ValueError, RuntimeError) as e:
        print(e)
        return 2
    print(evaluate.format_result(res))
    print(f"full result: {args.out}/eval_result.json · trajectories: uv run harbor view {args.out}/harbor-jobs")
    return 0


def _apple_silicon_rosetta_warning() -> str | None:
    """Task images are amd64. On Apple Silicon, Docker Desktop's default QEMU
    emulation crashes while the learner agent installs; Rosetta runs them."""
    import platform
    import sys
    from pathlib import Path

    if sys.platform != "darwin" or platform.machine() != "arm64":
        return None
    settings = Path.home() / "Library/Group Containers/group.com.docker/settings-store.json"
    try:
        enabled = json.loads(settings.read_text()).get("UseVirtualizationFrameworkRosetta")
    except (OSError, ValueError):
        return None
    if enabled:
        return None
    return ("WARNING: Docker Desktop's Rosetta emulation is off. Task containers are amd64 and will crash "
            "under the default emulation. Enable Docker Desktop → Settings → General → \"Use Rosetta for "
            "x86_64/amd64 emulation on Apple Silicon\", then Apply & restart.")


if __name__ == "__main__":
    raise SystemExit(main())
