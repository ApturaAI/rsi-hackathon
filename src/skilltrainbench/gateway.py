"""Metering gateway between the learner/graders and the model provider.

An OpenAI-compatible `/v1/chat/completions` forwarder. Every call reserves an
upper bound from a token pool, has `max_tokens` clamped to what the pool can
cover, and is reconciled against the provider's reported usage afterwards. A
call whose usage never arrives is charged its full reservation (fail-closed).
The learner containers only ever hold a per-run gateway key; the provider key
stays in this process.
"""

from __future__ import annotations

import asyncio
import contextvars
import hmac
import json
import math
import os
import re
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

DEFAULT_MAX_OUT = 4096
MARGIN = 64
# Non-streaming calls still waiting on the upstream after this long switch to a
# whitespace heartbeat (see `chat`); both stay well under the ~15 s egress cutoff.
HEARTBEAT_AFTER_S = 5.0
HEARTBEAT_EVERY_S = 5.0


# --------------------------------------------------------------- token pool

class BudgetExceeded(Exception):
    pass


@dataclass
class Reservation:
    rid: int
    amount: int


@dataclass
class BudgetMeter:
    """Token pool: reserve an upper bound before a call, reconcile after.
    `total_tokens=None` meters without ever refusing."""
    total_tokens: int | None
    _prompt: int = 0
    _completion: int = 0
    _cached: int = 0
    _reserved: dict[int, int] = field(default_factory=dict)
    _next_rid: int = 0
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def _cap(self) -> int:
        return sys.maxsize if self.total_tokens is None else int(self.total_tokens)

    def available(self) -> int:
        with self._lock:
            return max(0, self._cap() - self.spent() - sum(self._reserved.values()))

    def reserve(self, amount: int) -> Reservation:
        amount = int(amount)
        with self._lock:
            if amount <= 0 or amount > self.available():
                raise BudgetExceeded(f"cannot reserve {amount}: available {self.available()}")
            rid = self._next_rid
            self._next_rid += 1
            self._reserved[rid] = amount
        return Reservation(rid=rid, amount=amount)

    def reconcile(self, res: Reservation, prompt: int, completion: int, cached: int = 0) -> None:
        with self._lock:
            self._reserved.pop(res.rid, None)
            self._prompt += int(prompt)
            self._completion += int(completion)
            self._cached += int(cached)

    def reconcile_full(self, res: Reservation) -> None:
        """Fail-closed: charge the whole reservation (usage missing or interrupted)."""
        with self._lock:
            self._completion += int(self._reserved.pop(res.rid, res.amount))

    def spent(self) -> int:
        with self._lock:
            return self._prompt + self._completion

    def remaining(self) -> int | None:
        return None if self.total_tokens is None else max(0, int(self.total_tokens) - self.spent())

    def exhausted(self) -> bool:
        return self.total_tokens is not None and self.remaining() == 0

    def usage(self) -> dict:
        return {"prompt_tokens": self._prompt, "completion_tokens": self._completion,
                "cached_tokens": self._cached, "total_tokens": self.spent()}


# ------------------------------------------------------------------ ledger

# Tag (e.g. eval arm / task id) for the call in flight on this asyncio task.
_current_tag: contextvars.ContextVar[dict | None] = contextvars.ContextVar("current_tag", default=None)


class tagged:
    """`with tagged(arm="skill"): ...` — ledger rows recorded inside carry these fields."""

    def __init__(self, **fields) -> None:
        self._fields = fields
        self._token = None

    def __enter__(self) -> None:
        self._token = _current_tag.set({**(_current_tag.get() or {}), **self._fields})

    def __exit__(self, *exc) -> None:
        _current_tag.reset(self._token)


class AttemptTagRegistry:
    """Maps a per-attempt header value to tags, for calls made from inside a
    container (e.g. the grader), where the host's ContextVar cannot reach."""

    def __init__(self) -> None:
        self._tags: dict[str, dict] = {}
        self._lock = threading.Lock()

    @contextmanager
    def registered(self, attempt_id: str, **tags):
        with self._lock:
            if not attempt_id or attempt_id in self._tags:
                raise ValueError("attempt_id must be non-empty and unique")
            self._tags[attempt_id] = dict(tags)
        try:
            yield attempt_id
        finally:
            with self._lock:
                self._tags.pop(attempt_id, None)

    def resolve(self, attempt_id: str | None) -> dict:
        with self._lock:
            return dict(self._tags.get(attempt_id or "", {}))


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    k = (len(values) - 1) * (q / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return values[int(k)]
    return values[lo] * (hi - k) + values[hi] * (k - lo)


class Ledger:
    """One row per gateway call: the budget decision and timing, never content."""

    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._lock = threading.Lock()

    def record(self, entry: dict, *, tags: dict | None = None) -> None:
        tag = _current_tag.get()
        with self._lock:
            self._entries.append({"seq": len(self._entries), **entry, **(tag or {}), **(tags or {})})

    @property
    def entries(self) -> list[dict]:
        with self._lock:
            return list(self._entries)

    def to_jsonl(self) -> str:
        return "".join(json.dumps(e, separators=(",", ":")) + "\n" for e in self.entries)

    def summary(self) -> dict:
        es = self.entries
        priced = [e for e in es if e.get("cost_usd") is not None]
        by_model: dict[str, float] = {}
        for e in priced:
            m = e.get("model_resolved") or e.get("model") or "?"
            by_model[m] = round(by_model.get(m, 0.0) + float(e["cost_usd"]), 8)
        by_arm: dict[str, dict] = {}
        for e in es:
            if e.get("arm"):
                b = by_arm.setdefault(e["arm"], {"n_calls": 0, "prompt": 0, "completion": 0, "total_charged": 0})
                b["n_calls"] += 1
                b["prompt"] += int(e.get("prompt_tokens", 0) or 0)
                b["completion"] += int(e.get("completion_tokens", 0) or 0)
                b["total_charged"] += int(e.get("charged_tokens", 0) or 0)
        latencies = sorted(e["latency_ms"] for e in es if e.get("latency_ms") is not None)
        return {
            "n_calls": len(es),
            "cost": {
                # None (not 0.0) when nothing was priced: unknown spend is not free spend.
                "estimated_usd": round(sum(float(e["cost_usd"]) for e in priced), 8) if priced else None,
                "by_model": by_model,
                "n_priced": len(priced),
                "incomplete": any(e.get("status") in ("ok", "fail_closed") and e.get("cost_usd") is None
                                  for e in es),
            },
            **({"by_arm": by_arm} if by_arm else {}),
            "total_prompt": sum(int(e.get("prompt_tokens", 0) or 0) for e in es),
            "total_completion": sum(int(e.get("completion_tokens", 0) or 0) for e in es),
            "total_cached": sum(int(e.get("cached_tokens", 0) or 0) for e in es),
            "total_charged": sum(int(e.get("charged_tokens", 0) or 0) for e in es),
            "n_fail_closed": sum(1 for e in es if e.get("fail_closed")),
            "p50_latency_ms": _percentile(latencies, 50),
            "p95_latency_ms": _percentile(latencies, 95),
        }


# ------------------------------------------------------------------- proxy

def estimate_prompt_tokens(payload: dict) -> int:
    """Conservative prompt estimate (~3 chars/token + per-message overhead)."""
    total = 0
    for m in payload.get("messages", []) or []:
        c = m.get("content", "")
        if isinstance(c, str):
            total += len(c)
        elif isinstance(c, list):
            for part in c:
                total += len(str(part.get("text", part))) if isinstance(part, dict) else len(str(part))
    if payload.get("tools"):
        total += len(json.dumps(payload["tools"]))
    return max(1, total // 3) + 8 * len(payload.get("messages", []) or [])


def parse_usage(d: dict) -> tuple[int, int, int]:
    u = (d or {}).get("usage") or {}
    details = u.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens") or u.get("cache_read_input_tokens") or 0
    return int(u.get("prompt_tokens", 0) or 0), int(u.get("completion_tokens", 0) or 0), int(cached)


def _cost(headers, usage: dict | None, price: dict | None = None) -> float | None:
    """Report-only USD: a litellm cost header, else `usage.cost`, else usage × the
    provider's per-token `pricing` from /v1/models (Runware returns no per-call
    cost). None when unknown — never coerced to 0."""
    computed = None
    if price and usage:
        p, c, cached = parse_usage({"usage": usage})
        try:
            computed = ((p - cached) * float(price["prompt"]) + cached * float(price.get("input_cache_read", 0))
                        + c * float(price["completion"]))
        except (KeyError, TypeError, ValueError):
            pass
    for raw in (headers.get("x-litellm-response-cost"), (usage or {}).get("cost"), computed):
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value >= 0:
            return value
    return None


_FENCE = re.compile(r"\A\s*```[\w-]*\s*(.*?)\s*```\s*\Z", re.S)


def _unfence_json(data: dict) -> None:
    """Runware relays Anthropic models' ```json fences even when the request asked
    for `response_format`; OpenAI-style clients then fail to parse. Strip the
    fence only when what is inside is valid JSON."""
    for ch in data.get("choices") or []:
        msg = ch.get("message") if isinstance(ch, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        m = _FENCE.match(content) if isinstance(content, str) else None
        if m:
            try:
                json.loads(m.group(1))
            except ValueError:
                continue
            msg["content"] = m.group(1)


def _finish_reason(d: dict) -> str | None:
    if not isinstance(d, dict):
        return None
    for ch in d.get("choices") or []:
        if isinstance(ch, dict) and ch.get("finish_reason"):
            return ch["finish_reason"]
    return None


async def fetch_prices(client: httpx.AsyncClient) -> dict[str, dict]:
    """model id -> `pricing` (USD per token) from the provider's /v1/models; {} when
    unavailable, in which case costs stay None (unknown), never 0."""
    try:
        r = await client.get("/v1/models", timeout=30.0)
        data = (r.json().get("data") or []) if r.status_code < 400 else []
    except Exception:
        return {}
    if not isinstance(data, list):
        return {}
    return {m["id"]: m["pricing"] for m in data
            if isinstance(m, dict) and isinstance(m.get("id"), str) and isinstance(m.get("pricing"), dict)}


def build_app(meter: BudgetMeter, *, client: httpx.AsyncClient, ledger: Ledger | None = None,
              virtual_key: str | None = None, attempt_registry: AttemptTagRegistry | None = None,
              prices: dict[str, dict] | None = None) -> FastAPI:
    """`client` is the upstream (provider) client, carrying the provider key.
    `prices` maps model id -> per-token USD (`pricing` from /v1/models), for cost reporting."""
    app = FastAPI()
    prices = prices or {}
    app.state.budget_rejected = False

    def _auth_ok(request: Request) -> bool:
        if virtual_key is None:
            return True
        if hmac.compare_digest(request.headers.get("authorization") or "", f"Bearer {virtual_key}"):
            return True
        return hmac.compare_digest(request.headers.get("x-api-key") or "", virtual_key)

    @app.get("/health")
    async def health():
        return {"ok": True, "remaining": meter.remaining(), "usage": meter.usage()}

    @app.get("/v1/models")
    async def models(request: Request):
        if not _auth_ok(request):
            return JSONResponse({"error": {"type": "invalid_api_key"}}, status_code=401)
        r = await client.get("/v1/models")
        return Response(content=r.content, status_code=r.status_code, media_type="application/json")

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        t0 = time.monotonic()
        if not _auth_ok(request):
            return JSONResponse({"error": {"type": "invalid_api_key"}}, status_code=401)
        payload = await request.json()
        tags = attempt_registry.resolve(request.headers.get("x-stbench-attempt")) if attempt_registry else {}
        model = payload.get("model")
        price = prices.get(model) if isinstance(model, str) else None
        requested = int(payload.get("max_tokens") or payload.get("max_completion_tokens")
                        or payload.get("max_output_tokens") or DEFAULT_MAX_OUT)

        def _log(status, http_status, *, streaming=False, prompt=0, completion=0, cached=0, reserved=0,
                 charged=0, fail_closed=False, error_class=None, finish_reason=None, effective_max=None,
                 upstream_ttfb=None, upstream_total=None, model_resolved=None, cost_usd=None):
            if ledger is None:
                return
            ledger.record({
                "model": model,
                "model_resolved": model_resolved,
                "cost_usd": cost_usd,
                "streaming": bool(streaming),
                "status": status,
                "http_status": int(http_status),
                "error_class": error_class,
                "finish_reason": finish_reason,
                "prompt_tokens": int(prompt),
                "completion_tokens": int(completion),
                "cached_tokens": int(cached),
                "reserved_tokens": int(reserved),
                "charged_tokens": int(charged),
                "fail_closed": bool(fail_closed),
                "requested_max_tokens": int(requested),
                "effective_max_tokens": int(effective_max) if effective_max is not None else None,
                "max_tokens_clamped": bool(effective_max is not None and int(effective_max) < int(requested)),
                "latency_ms": round((time.monotonic() - t0) * 1000, 3),
                "upstream_ttfb_ms": round(upstream_ttfb * 1000, 3) if upstream_ttfb is not None else None,
                "upstream_total_ms": round(upstream_total * 1000, 3) if upstream_total is not None else None,
            }, tags=tags)

        def _reject(message: str, **log_kw):
            app.state.budget_rejected = True
            _log("budget_rejected", 402, **log_kw)
            return JSONResponse({"error": {"type": "budget_exceeded", "message": message}}, status_code=402)

        if int(payload.get("n", 1) or 1) > 1:
            _log("invalid_request", 400)
            return JSONResponse({"error": {"type": "invalid_request", "message": "n>1 not allowed (budget bound)"}},
                                status_code=400)
        avail = meter.available()
        if avail <= 0:
            return _reject("budget exhausted")
        prompt_est = estimate_prompt_tokens(payload)
        max_out = min(requested, avail - prompt_est - MARGIN)
        if max_out <= 0:
            return _reject("insufficient budget for request")
        payload["max_tokens"] = max_out
        payload.pop("max_completion_tokens", None)
        try:
            res = meter.reserve(prompt_est + max_out)
        except BudgetExceeded:
            return _reject("cannot reserve", effective_max=max_out)
        reserved = prompt_est + max_out
        streaming = bool(payload.get("stream"))
        if streaming:
            payload["stream_options"] = {**(payload.get("stream_options") or {}), "include_usage": True}

        try:
            accounted = {"done": False}
            if not streaming:
                async def _call() -> tuple[int, dict]:
                    """Upstream call plus its accounting; runs to completion even if
                    the client goes away, so every call is charged and logged."""
                    u_t0 = time.monotonic()
                    try:
                        r = await client.post("/v1/chat/completions", json=payload)
                    except BaseException as e:
                        accounted["done"] = True
                        meter.reconcile_full(res)
                        _log("error", 0, reserved=reserved, charged=reserved, fail_closed=True,
                             error_class=type(e).__name__, effective_max=max_out)
                        raise
                    u_total = time.monotonic() - u_t0
                    try:
                        data = r.json()
                    except Exception:
                        data = {}
                    if not isinstance(data, dict):
                        data = {}
                    model_resolved = data.get("model")
                    cost_usd = _cost(r.headers, data.get("usage"), price)
                    if r.status_code >= 400:
                        meter.reconcile(res, 0, 0, 0)
                        _log("upstream_error", r.status_code, reserved=reserved, effective_max=max_out,
                             upstream_total=u_total)
                        return r.status_code, data or {"error": {"message": "upstream error"}}
                    if payload.get("response_format"):
                        _unfence_json(data)
                    if not data.get("usage"):
                        meter.reconcile_full(res)
                        _log("fail_closed", r.status_code, reserved=reserved, charged=reserved, fail_closed=True,
                             finish_reason=_finish_reason(data), effective_max=max_out, upstream_total=u_total,
                             model_resolved=model_resolved, cost_usd=cost_usd)
                    else:
                        p, c, ca = parse_usage(data)
                        meter.reconcile(res, p, c, ca)
                        _log("ok", r.status_code, prompt=p, completion=c, cached=ca, reserved=reserved, charged=p + c,
                             finish_reason=_finish_reason(data), effective_max=max_out, upstream_total=u_total,
                             model_resolved=model_resolved, cost_usd=cost_usd)
                    return r.status_code, data

                call = asyncio.ensure_future(_call())
                done, _ = await asyncio.wait({call}, timeout=HEARTBEAT_AFTER_S)
                if done:
                    status_code, data = call.result()
                    return JSONResponse(data, status_code=status_code)

                # Harbor's task egress proxy drops a connection that carries no bytes
                # for ~15 s, and models often think longer than that. Commit to 200 and
                # send JSON-insignificant whitespace until the body is ready; the
                # client parses exactly the same JSON.
                async def _heartbeat_body():
                    while not call.done():
                        yield b" "
                        await asyncio.wait({call}, timeout=HEARTBEAT_EVERY_S)
                    _status, data = call.result()
                    yield json.dumps(data).encode()

                return StreamingResponse(_heartbeat_body(), status_code=200, media_type="application/json")

            # Streaming: relay every SSE line as it arrives, tap usage from it, and
            # reconcile when the stream ends (fail-closed if usage never came).
            state: dict = {"usage": None, "model": None, "finish_reason": None}
            u_t0 = time.monotonic()
            up = await client.send(client.build_request("POST", "/v1/chat/completions", json=payload), stream=True)
            if up.status_code >= 400:
                body = await up.aread()
                await up.aclose()
                meter.reconcile(res, 0, 0, 0)
                _log("upstream_error", up.status_code, streaming=True, reserved=reserved, effective_max=max_out,
                     upstream_total=time.monotonic() - u_t0)
                try:
                    err = json.loads(body)
                except Exception:
                    err = {"error": {"message": "upstream error"}}
                return JSONResponse(err, status_code=up.status_code)

            async def _relay():
                ttfb = None
                transport_error: Exception | None = None
                try:
                    async for line in up.aiter_lines():
                        if ttfb is None:
                            ttfb = time.monotonic() - u_t0
                        yield line + "\n"
                        s = line.strip()
                        if not s.startswith("data:"):
                            continue
                        body = s[5:].strip()
                        if not body or body == "[DONE]":
                            continue
                        try:
                            obj = json.loads(body)
                        except Exception:
                            continue
                        if isinstance(obj, dict):
                            if obj.get("usage"):
                                state["usage"] = obj["usage"]
                            if state["model"] is None and obj.get("model"):
                                state["model"] = obj["model"]
                            state["finish_reason"] = _finish_reason(obj) or state["finish_reason"]
                except Exception as e:
                    transport_error = e
                    yield ('data: {"error": {"type": "upstream_connection_error", '
                           '"message": "gateway lost the upstream connection mid-stream"}}\n\n')
                finally:
                    u_total = time.monotonic() - u_t0
                    cost_usd = _cost(up.headers, state["usage"], price)
                    if transport_error is not None:
                        meter.reconcile_full(res)
                        _log("error", 502, streaming=True, reserved=reserved, charged=reserved, fail_closed=True,
                             error_class=type(transport_error).__name__, effective_max=max_out,
                             upstream_ttfb=ttfb, upstream_total=u_total)
                    elif state["usage"] is not None:
                        p, c, ca = parse_usage({"usage": state["usage"]})
                        meter.reconcile(res, p, c, ca)
                        _log("ok", up.status_code, streaming=True, prompt=p, completion=c, cached=ca,
                             reserved=reserved, charged=p + c, finish_reason=state["finish_reason"],
                             effective_max=max_out, upstream_ttfb=ttfb, upstream_total=u_total,
                             model_resolved=state["model"], cost_usd=cost_usd)
                    else:
                        meter.reconcile_full(res)
                        _log("fail_closed", up.status_code, streaming=True, reserved=reserved, charged=reserved,
                             fail_closed=True, finish_reason=state["finish_reason"], effective_max=max_out,
                             upstream_ttfb=ttfb, upstream_total=u_total, model_resolved=state["model"],
                             cost_usd=cost_usd)
                    await up.aclose()

            return StreamingResponse(_relay(), media_type="text/event-stream")
        except Exception as e:
            if not accounted["done"]:
                meter.reconcile_full(res)
                _log("error", 0, streaming=streaming, reserved=reserved, charged=reserved, fail_closed=True,
                     error_class=type(e).__name__, effective_max=max_out)
            raise

    return app


# ------------------------------------------------------------ local server

def _docker_desktop() -> bool:
    return sys.platform in ("darwin", "win32")


def _bridge_gateway_ip() -> str:
    cmd = ["docker", "network", "inspect", "bridge", "--format", "{{(index .IPAM.Config 0).Gateway}}"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as e:
        raise RuntimeError("cannot run `docker network inspect bridge`; is Docker installed and running?") from e
    ip = (cp.stdout or "").strip()
    if cp.returncode != 0 or not ip:
        raise RuntimeError(f"cannot discover the Docker bridge gateway: {(cp.stderr or cp.stdout).strip()}")
    return ip


def _listen(host: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(128)
    sock.setblocking(False)
    return sock


class LocalGatewayServer:
    """Serves a gateway app on host loopback and at an address task containers
    can reach: `host.docker.internal` on Docker Desktop (macOS/Windows), the
    bridge gateway IP on a Linux Docker engine."""

    def __init__(self, app) -> None:
        self._app = app
        self._socks: list[socket.socket] = []
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task | None = None
        self.container_host: str | None = None
        self.port: int | None = None

    @property
    def container_url(self) -> str:
        return f"http://{self.container_host}:{self.port}"

    async def start(self) -> "LocalGatewayServer":
        override = (os.environ.get("STBENCH_DOCKER_BRIDGE_GATEWAY") or "").strip()
        desktop = not override and _docker_desktop()
        self.container_host = "host.docker.internal" if desktop else (override or _bridge_gateway_ip())
        loopback = _listen("127.0.0.1", 0)
        self.port = loopback.getsockname()[1]
        self._socks = [loopback]
        if not desktop:
            try:
                self._socks.append(_listen(self.container_host, self.port))
            except OSError as e:
                loopback.close()
                raise RuntimeError(f"cannot bind the gateway on {self.container_host}:{self.port}") from e
        # Agents keep a pooled connection open while they run a tool for minutes; the
        # 5 s uvicorn default closes it under them and the next call dies with
        # "Server disconnected without sending a response".
        config = uvicorn.Config(self._app, host="127.0.0.1", port=self.port, log_level="warning",
                                access_log=False, lifespan="off", timeout_keep_alive=3600)
        self._server = uvicorn.Server(config)
        self._task = asyncio.create_task(self._server.serve(sockets=self._socks))
        for _ in range(400):
            if self._server.started:
                return self
            if self._task.done():
                raise RuntimeError(f"local gateway failed to start: {self._task.exception()!r}")
            await asyncio.sleep(0.025)
        raise RuntimeError("local gateway did not start within 10s")

    async def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except Exception:
                self._task.cancel()
        for sock in self._socks:
            try:
                sock.close()
            except OSError:
                pass
        self._socks = []
