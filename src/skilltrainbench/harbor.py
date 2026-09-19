"""Run one Harbor attempt of a task with the frozen learner and read its result.

The task folder is staged exactly as in the organizers' scored runs: base images
and the tau2-bench checkout are pinned, and the learner container may reach only
the metering gateway. The learner and the graders never see a provider key; they
hold per-run gateway keys.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .tasks import Task, attempt_from_trial, read_task_toml, task_timeout

_QF_IMAGE = "doenermannti/finance-bench-sandbox@sha256:a6766c8b32cae3425feaddb8d9bac185de866323307290b7c74aed30f9c928ef"
_TAU3_IMAGE = "python:3.12-slim@sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79"
_HLE_IMAGE = "python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534"
# tau3 task images `git clone --depth=1` tau2-bench at build time; pinning the
# commit keeps every image on the same evaluator.
_TAU2_COMMIT = "672227c6b6"
_TAU3_CLONE_RE = re.compile(
    r'(?m)(&&\s*|^\s*RUN\s+)git clone --depth=1 ("\$\{TAU2_BENCH_REPO\}") ("\$\{TAU2_BENCH_ROOT\}")'
)
_JUDGE_THREAD_CAP = 4
_HARBOR_OVERHEAD_SEC = 900
_SETUP_TIMEOUT_MULT = "3"
_STAGED_SKILL_NAME = "stbench-skill"
_BLOCKED_ENV = frozenset({
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GOOGLE_API_KEY", "GEMINI_API_KEY",
    "OPENROUTER_API_KEY", "COHERE_API_KEY", "MISTRAL_API_KEY", "DEEPSEEK_API_KEY", "XAI_API_KEY",
    "AZURE_OPENAI_API_KEY", "AWS_BEARER_TOKEN_BEDROCK", "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_FORCE_OAUTH",
    "STBENCH_UPSTREAM_KEY", "STBENCH_UPSTREAM_BASE_URL",
    "ANTHROPIC_BASE_URL", "OPENAI_BASE_URL", "LLM_BASE_URL",
})


@dataclass(frozen=True)
class LearnerSettings:
    """Everything that pins the learner and the graders for one domain."""
    model: str
    agent: str
    agent_kwargs: dict = field(default_factory=dict)
    agent_timeout_s: int | None = None   # HealthBench only
    judge_model: str | None = None       # HealthBench / HLE grader
    judge_temperature: float = 0.0
    user_model: str | None = None        # tau3 simulated customer
    nl_assertions_model: str | None = None
    user_reasoning_effort: str | None = None


def default_skills_dir() -> str:
    from harbor.models.trial.paths import EnvironmentPaths

    return EnvironmentPaths().default_skills_dir.as_posix()


def _host(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"gateway URL must be HTTP(S) with a hostname: {url!r}")
    return parsed.hostname.lower().rstrip(".")


def _v1(url: str) -> str:
    base = url.rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def _set_toml(text: str, table: str, key: str, value: str) -> str:
    table_re = re.compile(rf"(?ms)^(?P<header>\[{re.escape(table)}\][^\n]*)\n(?P<body>.*?)(?=^\[[^\n]+\]|\Z)")
    match = table_re.search(text)
    if match is None:
        return text.rstrip() + f"\n\n[{table}]\n{key} = {value}\n"
    body = match.group("body")
    setting_re = re.compile(rf"(?m)^(?P<prefix>\s*{re.escape(key)}\s*=\s*).*$")
    if setting_re.search(body):
        body = setting_re.sub(rf"\g<prefix>{value}", body)
    else:
        body += f"{key} = {value}\n"
    return text[:match.start()] + match.group("header") + "\n" + body + text[match.end():]


def _pin_from(dockerfile: Path, pattern: str, image: str, what: str) -> None:
    text = dockerfile.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, rf"\g<1>{image}\g<2>", text, count=1)
    if count != 1:
        raise ValueError(f"{what} task Dockerfile has an unexpected base image")
    dockerfile.write_text(updated, encoding="utf-8")


def _edit_task_toml(task_dir: Path, settings: tuple[tuple[str, str, str], ...]) -> None:
    path = task_dir / "task.toml"
    text = path.read_text(encoding="utf-8")
    for table, key, value in settings:
        text = _set_toml(text, table, key, value)
    path.write_text(text, encoding="utf-8")


def egress_allowlist_supported() -> bool:
    """Harbor can only enforce `network_mode = "allowlist"` when the Docker daemon's
    kernel has nftables fib support; Docker Desktop (macOS/Windows) lacks it and
    harbor rejects the task outright. Cached by harbor: one `docker run alpine`."""
    from harbor.environments.docker.docker import DockerEnvironment

    return DockerEnvironment._egress_control_kernel_support()


def stage_task(task: Task, dst: Path, *, gateway_url: str, aux_url: str | None,
               settings: LearnerSettings) -> None:
    shutil.copytree(task.dir, dst)
    # ponytail: public egress where allowlist is unsupported; organizers' Linux runs keep it
    enforce = egress_allowlist_supported()
    learner_only = (("agent", "network_mode", '"allowlist"'),
                    ("agent", "allowed_hosts", json.dumps([_host(gateway_url)]))) if enforce else ()
    if task.benchmark == "qfbench":
        _pin_from(dst / "environment" / "Dockerfile",
                  r"(?mi)^(\s*FROM\s+)doenermannti/finance-bench-sandbox(?::latest|@sha256:[0-9a-f]{64})(\s*(?:AS\s+\S+)?\s*)$",
                  _QF_IMAGE, "QF")
        _edit_task_toml(dst, learner_only)
    elif task.benchmark == "hlebench":
        _pin_from(dst / "environment" / "Dockerfile",
                  r"(?mi)^(\s*FROM\s+)python:3\.11-slim(\s*(?:AS\s+\S+)?\s*)$", _HLE_IMAGE, "HLE")
        _edit_task_toml(dst, learner_only)
    elif task.benchmark == "tau3bench":
        for relative in ("environment/Dockerfile", "environment/runtime-server/Dockerfile"):
            dockerfile = dst / relative
            text = dockerfile.read_text(encoding="utf-8")
            froms = list(re.finditer(r"(?mi)^\s*FROM\s+(\S+)(?:\s+AS\s+\S+)?\s*$", text))
            if len(froms) != 1 or froms[0].group(1) not in {"python:3.12-slim", _TAU3_IMAGE}:
                raise ValueError(f"tau3 task {relative} must inherit from python:3.12-slim")
            start, end = froms[0].span(1)
            text, count = _TAU3_CLONE_RE.subn(
                rf"\g<1>git clone \g<2> \g<3> && git -C \g<3> checkout {_TAU2_COMMIT}",
                text[:start] + _TAU3_IMAGE + text[end:], count=1)
            if count != 1:
                raise ValueError(f"tau3 task {relative} must clone tau2-bench with `git clone --depth=1`")
            dockerfile.write_text(text, encoding="utf-8")
    elif task.benchmark == "healthbench":
        if not aux_url:
            raise ValueError("HealthBench staging requires the grader gateway URL")
        network = (
            ("agent", "network_mode", '"allowlist"'),
            ("agent", "allowed_hosts", json.dumps([_host(gateway_url)])),
            ("verifier", "network_mode", '"allowlist"'),
            ("verifier", "allowed_hosts", json.dumps([_host(aux_url)])),
        ) if enforce else ()
        _edit_task_toml(dst, (
            ("environment", "cpus", "1"),
            ("environment", "memory_mb", "512"),
            ("agent", "timeout_sec", str(settings.agent_timeout_s or 300)),
            *network,
            ("verifier.env", "STBENCH_JUDGE_BASE_URL", '"${STBENCH_JUDGE_BASE_URL}"'),
            ("verifier.env", "STBENCH_JUDGE_API_KEY", '"${STBENCH_JUDGE_API_KEY}"'),
            ("verifier.env", "STBENCH_JUDGE_MODEL", '"${STBENCH_JUDGE_MODEL}"'),
            ("verifier.env", "STBENCH_JUDGE_TEMPERATURE", '"${STBENCH_JUDGE_TEMPERATURE}"'),
            ("verifier.env", "STBENCH_JUDGE_ATTEMPT", '"${STBENCH_JUDGE_ATTEMPT}"'),
            ("verifier.env", "STBENCH_JUDGE_THREADS", '"${STBENCH_JUDGE_THREADS}"'),
        ))
        grader = dst / "tests" / "grader_config.json"
        try:
            config = json.loads(grader.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("HealthBench grader_config.json is invalid") from error
        if not isinstance(config, dict):
            raise ValueError("HealthBench grader_config.json must contain an object")
        config["grader_model"] = settings.judge_model or ""
        config["temperature"] = settings.judge_temperature
        grader.write_text(json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _grader_env(task: Task, settings: LearnerSettings, aux_url: str | None, aux_key: str | None,
                attempt_id: str) -> dict[str, str]:
    """Env the verifier (grader) and the tau3 simulated customer read; it points
    them at the separately metered grader gateway."""
    if task.benchmark == "qfbench":
        return {}
    base, key = _v1(aux_url or ""), aux_key or ""
    if task.benchmark == "healthbench":
        return {
            "STBENCH_JUDGE_BASE_URL": base,
            "STBENCH_JUDGE_API_KEY": key,
            "STBENCH_JUDGE_MODEL": settings.judge_model or "",
            "STBENCH_JUDGE_TEMPERATURE": str(settings.judge_temperature),
            "STBENCH_JUDGE_ATTEMPT": attempt_id,
            "STBENCH_JUDGE_THREADS": str(min(os.cpu_count() or 10, _JUDGE_THREAD_CAP)),
        }
    if task.benchmark == "hlebench":
        return {"OPENAI_API_KEY": key, "OPENAI_BASE_URL": base, "JUDGE_MODEL": settings.judge_model or ""}

    def _litellm(model: str | None) -> str:
        model = model or ""
        return model if model.startswith("openai/") else f"openai/{model}"

    return {
        "OPENAI_API_KEY": key,
        "OPENAI_BASE_URL": base,
        "TAU2_USER_MODEL": _litellm(settings.user_model),
        "TAU2_NL_ASSERTIONS_MODEL": _litellm(settings.nl_assertions_model),
        "TAU2_USER_REASONING_EFFORT": settings.user_reasoning_effort or "low",
        "TAU2_USER_TEMPERATURE": "",
        "TAU2_USER_LLM_ARGS_JSON": "",
    }


def _harbor_executable() -> str:
    found = shutil.which("harbor")
    if found:
        return found
    sibling = Path(sys.executable).resolve().parent / "harbor"
    return str(sibling) if sibling.is_file() else "harbor"


def _safe_slug(text: str, max_length: int = 180) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-") or "task"
    if len(slug) <= max_length:
        return slug
    return f"{slug[:max_length - 9]}-{hashlib.sha256(slug.encode()).hexdigest()[:8]}"


def build_command(task: Task, task_dir: Path, *, settings: LearnerSettings, gateway_url: str,
                  gateway_key: str, jobs_dir: Path, job_name: str,
                  staged_skill: Path | None) -> tuple[list[str], dict[str, str]]:
    """The `harbor run` command line and the agent env it passes to the learner."""
    agent = settings.agent
    if agent.startswith("openhands"):
        # OpenHands' OpenAI route appends /chat/completions to its base URL.
        llm_base = _v1(gateway_url)
        model = settings.model if "/" in settings.model else f"openai/{settings.model}"
    else:
        llm_base, model = gateway_url.rstrip("/"), settings.model
    agent_env = {
        "OPENAI_BASE_URL": gateway_url,
        "OPENAI_API_KEY": gateway_key,
        "ANTHROPIC_BASE_URL": gateway_url,
        "ANTHROPIC_API_KEY": gateway_key,
        "ANTHROPIC_AUTH_TOKEN": gateway_key,
        "LLM_BASE_URL": llm_base,
        "LLM_API_KEY": gateway_key,
        "STBENCH_TASK_ID": task.id,
    }
    cmd = [
        _harbor_executable(), "run",
        "-p", str(task_dir),
        "-m", model,
        "-a", agent,
        "-e", "docker",
        "-o", str(jobs_dir),
        "--job-name", job_name,
        "-n", "1",
        "-y",
        "--agent-setup-timeout-multiplier", _SETUP_TIMEOUT_MULT,
    ]
    if staged_skill is not None:
        cmd.extend(["--skill", str(staged_skill)])
    for key, val in sorted(settings.agent_kwargs.items()):
        encoded = json.dumps(val) if agent.startswith("openhands") and isinstance(val, (list, dict)) else val
        cmd.extend(["--ak", f"{key}={encoded}"])
    for key, val in sorted(agent_env.items()):
        cmd.extend(["--ae", f"{key}={val}"])
    return cmd, agent_env


def _child_env(overrides: dict[str, str]) -> dict[str, str]:
    """The Harbor process env: no provider credentials or routing overrides."""
    env = {
        k: v for k, v in os.environ.items()
        if k not in _BLOCKED_ENV and not k.endswith("_API_KEY") and not k.endswith("_AUTH_TOKEN")
    }
    env.update(overrides)
    return env


async def _terminate(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            if os.name == "posix":
                os.killpg(process.pid, sig)
            else:  # pragma: no cover
                process.kill()
            await asyncio.wait_for(process.wait(), timeout=15)
            return
        except ProcessLookupError:
            return
        except (OSError, TimeoutError):
            continue


async def _run_harbor(cmd: list[str], timeout_s: int, env: dict[str, str]) -> dict:
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=env, start_new_session=(os.name == "posix"),
        )
    except OSError as e:
        return {"returncode": None, "timed_out": False, "exec_error": type(e).__name__, "stderr": str(e)}
    output = asyncio.create_task(process.communicate())
    try:
        _stdout, stderr = await asyncio.wait_for(asyncio.shield(output), timeout=timeout_s)
    except TimeoutError:
        await _terminate(process)
        try:
            _stdout, stderr = await asyncio.wait_for(output, timeout=15)
        except TimeoutError:
            stderr = b""
        return {"returncode": process.returncode, "timed_out": True, "exec_error": None,
                "stderr": stderr.decode("utf-8", errors="replace")}
    except asyncio.CancelledError:
        await asyncio.shield(_terminate(process))
        raise
    return {"returncode": process.returncode, "timed_out": False, "exec_error": None,
            "stderr": stderr.decode("utf-8", errors="replace")}


def _find_trial(job_dir: Path) -> tuple[Path, dict] | None:
    if not job_dir.is_dir():
        return None
    for child in sorted(job_dir.iterdir()):
        path = child / "result.json"
        if child.is_dir() and path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict):
                return child, data
    return None


def _failed(task: Task, status: str, error_class: str, **artifacts) -> dict:
    return {"task_id": task.id, "status": status, "answer": "", "artifacts": artifacts, "error_class": error_class}


async def run_attempt(task: Task, skill_dir: Path | None, *, settings: LearnerSettings,
                      gateway_url: str, gateway_key: str, jobs_dir: Path,
                      aux_url: str | None = None, aux_key: str | None = None,
                      aux_exhausted=None, attempt_id: str = "") -> dict:
    """One Harbor trial of `task` with `skill_dir` mounted (None = no skill)."""
    jobs_dir = Path(jobs_dir).expanduser().resolve()
    job_name = f"{_safe_slug(task.id)}-{secrets.token_hex(4)}"
    timeout_s = max(1, int(task.timeout_sec or 240))
    try:
        jobs_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"stb-{task.benchmark}-{_safe_slug(task.id)}-") as temp:
            staging = Path(temp)
            staged_task = staging / "task"
            stage_task(task, staged_task, gateway_url=gateway_url, aux_url=aux_url, settings=settings)
            if task.benchmark == "healthbench":
                timeout_s = max(1, int(task_timeout(read_task_toml(staged_task)) or task.timeout_sec or 240))
            staged_skill = None
            if skill_dir is not None and (Path(skill_dir) / "SKILL.md").is_file():
                staged_skill = staging / _STAGED_SKILL_NAME
                shutil.copytree(skill_dir, staged_skill)
            cmd, agent_env = build_command(
                task, staged_task, settings=settings, gateway_url=gateway_url, gateway_key=gateway_key,
                jobs_dir=jobs_dir, job_name=job_name, staged_skill=staged_skill,
            )
            env = _child_env({**agent_env, **_grader_env(task, settings, aux_url, aux_key, attempt_id)})
            run = await _run_harbor(cmd, timeout_s + _HARBOR_OVERHEAD_SEC, env)
    except ValueError as e:
        return _failed(task, "infra_error", f"runtime_harbor_config_invalid:{e}")
    except OSError as e:
        return _failed(task, "infra_error", f"runtime_skill_stage_error:{type(e).__name__}")
    aux_spent = aux_exhausted is not None and aux_exhausted()
    found = _find_trial(jobs_dir / job_name)
    if found is not None:
        attempt = attempt_from_trial(task, *found)
        if aux_spent:
            attempt.update(status="infra_error", answer="", error_class="runtime_simulator_budget_exhausted")
        return attempt
    job_dir = str(jobs_dir / job_name)
    if aux_spent:
        return _failed(task, "infra_error", "runtime_simulator_budget_exhausted", job_dir=job_dir)
    if run["timed_out"]:
        return _failed(task, "timeout", "runtime_timeout", job_dir=job_dir)
    if run["exec_error"]:
        return _failed(task, "infra_error", "runtime_exec_error", job_dir=job_dir)
    return _failed(task, "infra_error", f"harbor_no_trial_result_exit_{run['returncode']}", job_dir=job_dir,
                   stderr_tail=run["stderr"][-2000:])
