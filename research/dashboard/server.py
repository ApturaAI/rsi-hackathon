#!/usr/bin/env python3
"""Local research dashboard. Reads completed runs; never launches evals."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.dashboard.catalog import load_dataset, load_experiments, load_run, overview

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
HOST = "127.0.0.1"
PORT = 8787


def _json_bytes(payload: object, status: int = 200) -> tuple[int, bytes, str]:
    return status, json.dumps(payload, default=str).encode("utf-8"), "application/json; charset=utf-8"


def route(path: str) -> tuple[int, bytes, str] | None:
    if path == "/api/overview":
        return _json_bytes(overview())
    if path == "/api/runs":
        data = overview()
        return _json_bytes({"runs": data["runs"], "domains": data["domains"]})
    if path == "/api/dataset":
        return _json_bytes(load_dataset())
    if path == "/api/experiments":
        return _json_bytes({"experiments": load_experiments()})
    if path.startswith("/api/run/"):
        name = unquote(path[len("/api/run/"):].strip("/"))
        if not name or "/" in name or name in {".", ".."}:
            return _json_bytes({"error": "invalid run name"}, 400)
        run = load_run(name)
        if run is None:
            return _json_bytes({"error": f"run not found: {name}"}, 404)
        return _json_bytes(run)
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        api = route(path)
        if api is not None:
            self._send(*api)
            return
        rel = "index.html" if path in {"/", "/index.html"} else path.lstrip("/")
        target = (STATIC / rel).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            self._send(404, b"not found\n", "text/plain; charset=utf-8")
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"research dashboard  http://{args.host}:{args.port}")
    print("reads local files only; Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
