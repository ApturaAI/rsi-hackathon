"""`hackathon.toml` (the pinned learner), training data, and skill checks."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .harbor import LearnerSettings, default_skills_dir
from .tasks import REQUIRED_FILES

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "hackathon.toml"
_BENCHMARKS = frozenset(REQUIRED_FILES)


@dataclass(frozen=True)
class DomainCfg:
    name: str
    benchmark: str
    dataset_dir: Path
    max_iterations: int | None = None
    agent_timeout_s: int | None = None
    judge_model: str | None = None
    judge_temperature: float = 0.0
    judge_budget_tokens: int | None = None
    eval_budget_tokens: int = 2_000_000
    user_model: str | None = None
    nl_assertions_model: str | None = None
    user_reasoning_effort: str | None = None


@dataclass(frozen=True)
class HackathonCfg:
    path: Path
    hf_repo: str
    hf_revision: str
    data_dir: Path
    learner_model: str
    harbor_agent: str
    agent_kwargs: dict
    concurrency: int
    upstream_base_url: str
    upstream_key_env: str
    max_total_bytes: int
    max_files: int
    domains: dict[str, DomainCfg] = field(default_factory=dict)

    def domain(self, name: str) -> DomainCfg:
        try:
            return self.domains[name]
        except KeyError:
            raise ValueError(f"unknown domain {name!r}; have {sorted(self.domains)}") from None


def _path(root: Path, raw: str) -> Path:
    p = Path(raw).expanduser()
    return p if p.is_absolute() else root / p


def load_config(path: str | Path | None = None) -> HackathonCfg:
    p = Path(path) if path else DEFAULT_CONFIG
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported hackathon config schema in {p}")
    root = p.resolve().parent
    source, learner, upstream = data.get("data", {}), data["learner"], data["upstream"]
    submission = data.get("submission", {})
    data_dir = _path(root, source.get("local_dir", "dataset/hackathon"))
    domains = {}
    for name, raw in (data.get("domains") or {}).items():
        if raw["benchmark"] not in _BENCHMARKS:
            raise ValueError(f"domain {name!r}: benchmark must be one of {sorted(_BENCHMARKS)}")
        domains[name] = DomainCfg(
            name=name,
            benchmark=raw["benchmark"],
            dataset_dir=_path(root, raw["dataset_dir"]) if raw.get("dataset_dir") else data_dir / name / "tasks",
            max_iterations=raw.get("max_iterations"),
            agent_timeout_s=raw.get("agent_timeout_s"),
            judge_model=raw.get("judge_model"),
            judge_temperature=float(raw.get("judge_temperature", 0.0)),
            judge_budget_tokens=int(raw["judge_budget_tokens"]) if raw.get("judge_budget_tokens") else None,
            eval_budget_tokens=int(raw.get("eval_budget_tokens", 2_000_000)),
            user_model=raw.get("user_model"),
            nl_assertions_model=raw.get("nl_assertions_model"),
            user_reasoning_effort=raw.get("user_reasoning_effort"),
        )
    return HackathonCfg(
        path=p,
        hf_repo=source.get("hf_repo", ""),
        hf_revision=source.get("hf_revision", "main"),
        data_dir=data_dir,
        learner_model=learner["model"],
        harbor_agent=learner.get("harbor_agent", "openhands-sdk"),
        agent_kwargs=dict(learner.get("agent_kwargs") or {}),
        concurrency=int(learner.get("concurrency", 4)),
        upstream_base_url=upstream["base_url"].rstrip("/"),
        upstream_key_env=upstream.get("key_env", "STBENCH_UPSTREAM_KEY"),
        max_total_bytes=int(submission.get("max_total_bytes", 1_000_000)),
        max_files=int(submission.get("max_files", 200)),
        domains=domains,
    )


def learner_settings(cfg: HackathonCfg, domain: DomainCfg) -> LearnerSettings:
    openhands = cfg.harbor_agent.startswith("openhands")
    kwargs = dict(cfg.agent_kwargs)
    if domain.benchmark == "healthbench":
        kwargs["max_iterations" if openhands else "max_turns"] = domain.max_iterations or 4
    elif domain.max_iterations is not None and openhands:
        kwargs["max_iterations"] = domain.max_iterations
    if openhands:
        # OpenHands loads skills only from the paths it is told about.
        kwargs["skill_paths"] = [default_skills_dir()]
    return LearnerSettings(
        model=cfg.learner_model,
        agent=cfg.harbor_agent,
        agent_kwargs=kwargs,
        agent_timeout_s=domain.agent_timeout_s,
        judge_model=domain.judge_model,
        judge_temperature=domain.judge_temperature,
        user_model=domain.user_model,
        nl_assertions_model=domain.nl_assertions_model,
        user_reasoning_effort=domain.user_reasoning_effort,
    )


# ---------------------------------------------------------------------- data

def pull_data(cfg: HackathonCfg, *, token: str | None = None) -> Path:
    if not cfg.hf_repo:
        raise ValueError("hackathon.toml [data].hf_repo is not set yet — the training data is not published")
    import time

    import httpx
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    print(f"downloading {cfg.hf_repo}@{cfg.hf_revision} into {cfg.data_dir} "
          "(many small files; a rerun resumes where it stopped)")
    # The dataset is ~30k small files; one stalled metadata call otherwise surfaces as a traceback.
    attempts = 5
    for n in range(1, attempts + 1):
        try:
            snapshot_download(repo_id=cfg.hf_repo, repo_type="dataset", revision=cfg.hf_revision,
                              local_dir=str(cfg.data_dir), token=token)
            break
        except (httpx.TransportError, LocalEntryNotFoundError) as e:
            if n == attempts:
                raise
            print(f"download interrupted ({type(e).__name__}); resuming, retry {n} of {attempts - 1}")
            time.sleep(2 * n)
    return cfg.data_dir


def task_names(domain: DomainCfg, *, task_ids: list[str] | None = None, limit: int | None = None) -> list[str]:
    """Training tasks = the task folders present under the domain's dataset dir."""
    root = domain.dataset_dir
    if not root.is_dir():
        raise ValueError(f"no tasks at {root} — run `stbench data pull` first")
    available = sorted(p.name for p in root.iterdir()
                       if p.is_dir() and not p.is_symlink() and (p / "task.toml").is_file())
    if task_ids:
        unknown = [t for t in task_ids if t not in available]
        if unknown:
            raise ValueError(f"unknown {domain.name} tasks: {unknown[:5]}")
        names = list(task_ids)
    else:
        names = available
    names = names if limit is None else names[: max(0, limit)]
    if not names:
        raise ValueError(f"no tasks selected under {root}")
    return names


# --------------------------------------------------------------- skill check

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_EXTERNAL = re.compile(
    r"(https?://(?!localhost|127\.0\.0\.1)[\w.-]+\.[a-z]{2,}[^\s)\"']*"
    r"|\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}"
    r"|\b[A-Z][A-Z0-9_]*_API_KEY\b)"
)


def check_skill(skill_dir: str | Path, cfg: HackathonCfg) -> dict:
    """Errors reject a submission; warnings flag it for review (a skill's tools must
    run offline inside the task container: no external services, no credentials)."""
    d = Path(skill_dir)
    if not d.is_dir():
        return {"ok": False, "errors": [f"not a directory: {d}"], "warnings": []}
    errors: list[str] = []
    warnings: list[str] = []
    files = []
    for p in sorted(d.rglob("*")):
        if p.is_symlink():
            errors.append(f"symlink not allowed: {p.relative_to(d).as_posix()}")
        elif p.is_file():
            files.append(p)
    total = sum(p.stat().st_size for p in files)
    if len(files) > cfg.max_files:
        errors.append(f"{len(files)} files exceeds the limit of {cfg.max_files}")
    if total > cfg.max_total_bytes:
        errors.append(f"{total} bytes exceeds the limit of {cfg.max_total_bytes}")
    skill_md = d / "SKILL.md"
    if not skill_md.is_file():
        errors.append("missing SKILL.md at the skill root")
    else:
        m = _FRONTMATTER.match(skill_md.read_text(encoding="utf-8", errors="replace"))
        if not m:
            errors.append("SKILL.md must start with YAML frontmatter (--- name/description ---)")
        else:
            keys = {line.split(":", 1)[0].strip() for line in m.group(1).splitlines() if ":" in line}
            errors.extend(f"SKILL.md frontmatter is missing `{k}`" for k in ("name", "description") if k not in keys)
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for hit in sorted(set(_EXTERNAL.findall(text)))[:3]:
            warnings.append(f"{p.relative_to(d).as_posix()}: external endpoint or credential reference {hit!r}")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "n_files": len(files), "total_bytes": total}

