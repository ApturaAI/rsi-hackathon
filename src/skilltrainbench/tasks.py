"""Harbor task folders for the four benchmarks, and how an attempt is scored."""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

_HEALTHBENCH_FILES = (
    "instruction.md",
    "task.toml",
    "environment/Dockerfile",
    "tests/__init__.py",
    "tests/example.json",
    "tests/grader_config.json",
    "tests/run_grader.py",
    "tests/simple_evals_shim/__init__.py",
    "tests/simple_evals_shim/blobfile.py",
    "tests/simple_evals_shim/common.py",
    "tests/simple_evals_shim/grade.py",
    "tests/simple_evals_shim/healthbench_eval.py",
    "tests/simple_evals_shim/numpy.py",
    "tests/simple_evals_shim/pandas.py",
    "tests/simple_evals_shim/sampler/__init__.py",
    "tests/simple_evals_shim/sampler/chat_completion_sampler.py",
    "tests/simple_evals_shim/types.py",
    "tests/test.sh",
)

# benchmark -> files every task folder must contain
REQUIRED_FILES: dict[str, tuple[str, ...]] = {
    "qfbench": (
        "instruction.md",
        "task.toml",
        "environment/Dockerfile",
        "tests/test.sh",
        "tests/test_outputs.py",
    ),
    "healthbench": _HEALTHBENCH_FILES,
    "tau3bench": (
        "instruction.md",
        "task.toml",
        "environment/Dockerfile",
        "environment/docker-compose.yaml",
        "environment/runtime-server/Dockerfile",
        "environment/runtime-server/server.py",
        "environment/runtime-server/task_config.json",
        "tests/test.sh",
        "tests/evaluate.py",
        "tests/config.json",
    ),
    "hlebench": (
        "instruction.md",
        "task.toml",
        "environment/Dockerfile",
        "environment/entrypoint.sh",
        "environment/workspace/instruction.md",
        "tests/test.sh",
        "tests/test_judge.py",
        "tests/answer.txt",
        "tests/metadata.json",
        "tests/question.txt",
    ),
}
# HealthBench scores are rubric fractions; the others are pass/fail.
FRACTIONAL = frozenset({"healthbench"})
PASS_REWARD = 1.0


@dataclass(frozen=True)
class Task:
    id: str
    name: str
    benchmark: str
    dir: Path
    timeout_sec: float | None

    @property
    def fractional(self) -> bool:
        return self.benchmark in FRACTIONAL


def read_task_toml(task_dir: Path) -> dict:
    path = task_dir / "task.toml"
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise RuntimeError(f"malformed task.toml: {path}: {error}") from error


def task_timeout(task_toml: dict) -> float | None:
    values = []
    for section in ("agent", "verifier"):
        block = task_toml.get(section)
        if isinstance(block, dict):
            value = block.get("timeout_sec")
            if isinstance(value, (int, float)) and value > 0:
                values.append(float(value))
    return max(values) if values else None


def load_task(benchmark: str, tasks_root: Path, name: str) -> Task:
    root = Path(tasks_root).expanduser().resolve()
    if not name or Path(name).name != name:
        raise ValueError(f"invalid task name {name!r}")
    task_dir = root / name
    if task_dir.is_symlink() or not task_dir.is_dir() or task_dir.resolve().parent != root:
        raise ValueError(f"{benchmark} task {name!r} is not a directory in {root}")
    missing = [f for f in REQUIRED_FILES[benchmark] if not (task_dir / f).is_file()]
    if missing:
        raise RuntimeError(f"{benchmark} task {name!r} missing required files: {', '.join(missing)}")
    return Task(
        id=f"{benchmark}-train-{name}",
        name=name,
        benchmark=benchmark,
        dir=task_dir,
        timeout_sec=task_timeout(read_task_toml(task_dir)),
    )


def finite_reward(reward: object) -> float | None:
    if isinstance(reward, bool) or not isinstance(reward, (int, float)):
        return None
    value = float(reward)
    return value if math.isfinite(value) else None


def is_pass(reward: object) -> bool:
    """Pass/fail benchmarks count only a full reward as a pass."""
    if isinstance(reward, bool):
        return reward
    if not isinstance(reward, (int, float)):
        return False
    return float(reward) >= PASS_REWARD


def score(task: Task, attempt: dict) -> float | None:
    """Score of one attempt: the rubric fraction (HealthBench) or 1.0/0.0.
    None means the grader could not grade it; it is excluded, never a fail."""
    status = attempt.get("status")
    artifacts = attempt.get("artifacts") if isinstance(attempt.get("artifacts"), dict) else {}
    verifier = artifacts.get("verifier")
    if task.fractional:
        verifier_status = attempt.get("verifier_status")
        if verifier_status == "budget_exhausted":
            raise RuntimeError("grader budget pool exhausted during verifier grading")
        if verifier_status == "invalidated":
            return None if not isinstance(verifier, dict) else 0.0
        if verifier_status != "ok":
            return 0.0
    if attempt.get("task_id") != task.id or status != "ok" or not isinstance(verifier, dict):
        return 0.0
    if verifier.get("task_id") not in (None, task.id):
        return 0.0
    if task.fractional:
        return finite_reward(verifier.get("reward")) or 0.0
    return 1.0 if verifier.get("success") is True else 0.0


def verifier_status(trial_dir: Path) -> str:
    try:
        value = (trial_dir / "verifier" / "grading_status").read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "absent"
    return value if value in {"ok", "invalidated", "budget_exhausted"} else "absent"


_BUDGET_LOG_MARKERS = (
    "budget_exceeded",
    "budget exhausted",
    "insufficient budget",
    "cannot reserve",
    "budget_exhausted",
    "402 payment required",
    "status code: 402",
    '"status": 402',
    "status_402",
    "api error: 402",
)


def _agent_logs_show_budget_exhausted(trial_dir: Path) -> bool:
    agent_dir = trial_dir / "agent"
    if not agent_dir.is_dir():
        return False
    for p in agent_dir.rglob("*"):
        if not p.is_file() or p.stat().st_size > 5_000_000:
            continue
        try:
            low = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        if any(m in low for m in _BUDGET_LOG_MARKERS):
            return True
    return False


def attempt_from_trial(task: Task, trial_dir: Path, result: dict) -> dict:
    """Turn a Harbor trial (result.json + verifier files) into an attempt record."""
    base = {"task_id": task.id, "answer": "", "artifacts": {"trial_dir": str(trial_dir)}}
    status_file = verifier_status(trial_dir)
    if task.fractional:
        base["verifier_status"] = status_file
        response = trial_dir / "agent" / "response.txt"
        try:
            resolved = response.resolve(strict=True)
            resolved.relative_to(trial_dir.resolve(strict=True))
            base["answer"] = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            pass
    vr = result.get("verifier_result") if isinstance(result.get("verifier_result"), dict) else {}
    rewards = vr.get("rewards") if isinstance(vr.get("rewards"), dict) else {}
    raw_reward = rewards.get("reward")
    if task.fractional:
        reward = finite_reward(raw_reward)
        has_reward = reward is not None
    else:
        has_reward = isinstance(raw_reward, (int, float)) and not isinstance(raw_reward, bool)
        reward = float(raw_reward) if has_reward else None
    exc = result.get("exception_info")
    if task.fractional and status_file == "budget_exhausted":
        raise RuntimeError("grader budget pool exhausted during verifier grading")
    if task.fractional and has_reward and status_file != "ok":
        return {**base, "status": "infra_error", "error_class": "harbor_inconsistent_reward_status"}
    if isinstance(exc, dict) and exc:
        exc_type = str(exc.get("exception_type") or "unknown")
        if not has_reward and not (task.fractional and status_file == "invalidated"):
            status = "timeout" if "timeout" in exc_type.lower() else "infra_error"
            return {**base, "status": status, "error_class": f"harbor_exception:{exc_type}"[:120]}
    if not has_reward and task.fractional:
        if status_file == "invalidated":
            return {**base, "status": "ok", "error_class": None}
        error_class = "harbor_invalid_reward" if raw_reward is not None else "harbor_missing_reward"
        return {**base, "status": "infra_error", "error_class": error_class}
    if not has_reward:
        return {**base, "status": "invalid_output", "error_class": "harbor_missing_reward"}
    if reward < 1.0 and _agent_logs_show_budget_exhausted(trial_dir):
        return {**base, "status": "budget_exhausted", "error_class": "runtime_budget_exhausted"}
    base["artifacts"]["verifier"] = {"success": is_pass(reward), "task_id": task.id, "reward": reward}
    return {**base, "status": "ok", "error_class": None}
