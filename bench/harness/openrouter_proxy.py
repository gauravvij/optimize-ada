#!/usr/bin/env python3
"""Proxy between the SetupBench containers and OpenRouter's Anthropic-compatible API.

Why it exists: for deepseek/deepseek-v4-flash, OpenRouter's default routing picks the cheapest provider
(StreamLake), which returned EMPTY completions (1 stop token) for Ada's tool-carrying requests. Claude Code
cannot send provider preferences, so this proxy adds `provider.ignore` to every /v1/messages request. Nothing
else in the request is changed. It also writes one log line per call (generation id, timing, block kinds) so
each call can be tied to its provider and true cost afterwards (`fetch` mode). Bodies and headers, including
the API key, are never logged. Streaming is passed through chunk by chunk, so latency is not distorted.

  python3 openrouter_proxy.py serve --port 8765 --log-dir DIR [--ignore StreamLake,...]
  OPENROUTER_API_KEY=... python3 openrouter_proxy.py fetch DIR      # calls.jsonl -> generations.jsonl
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UPSTREAM = "openrouter.ai"
DROP_REQUEST_HEADERS = {"host", "content-length", "accept-encoding", "connection", "transfer-encoding"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        started = time.monotonic()
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        info: dict = {"ts": round(time.time(), 3), "path": self.path}
        body = raw
        if urlsplit(self.path).path.endswith("/v1/messages"):  # the CLI appends ?beta=true
            try:
                request = json.loads(raw)
                provider = dict(request.get("provider") or {})
                if self.server.ignore:  # with no exclusion configured the request is passed through untouched
                    provider["ignore"] = sorted(set(provider.get("ignore") or []) | set(self.server.ignore))
                    request["provider"] = provider
                info.update(
                    model=request.get("model"), stream=bool(request.get("stream")),
                    tools=len(request.get("tools") or []), thinking=request.get("thinking"),
                    messages=len(request.get("messages") or []), provider_ignore=provider["ignore"],
                )
                try:  # Claude Code puts its session id in metadata.user_id; it ties each call to one task's trace
                    info["session_id"] = json.loads(request["metadata"]["user_id"]).get("session_id")
                except (KeyError, TypeError, ValueError):
                    pass
                body = json.dumps(request).encode()
            except ValueError:
                pass
        headers = {k: v for k, v in self.headers.items() if k.lower() not in DROP_REQUEST_HEADERS}
        headers["Content-Length"] = str(len(body))
        try:
            upstream = http.client.HTTPSConnection(UPSTREAM, timeout=600)
            upstream.request("POST", self.path, body, headers)
            response = upstream.getresponse()
        except Exception as exc:  # the CLI retries on 5xx
            info.update(status=502, error=f"{type(exc).__name__}:{exc}")
            self.server.log(info)
            self.send_error(502)
            return
        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() in ("content-type", "retry-after"):
                self.send_header(key, value)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        seen, first_byte = bytearray(), None
        try:
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    break
                first_byte = first_byte if first_byte is not None else time.monotonic() - started
                if len(seen) < 4_000_000:
                    seen += chunk
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            info["client_disconnected"] = True  # e.g. the harness removed the container at the time limit
        text = seen.decode("utf-8", "replace")
        generation = re.search(r'"id":\s*"(gen-[^"]+)"', text)
        stops = re.findall(r'"stop_reason":\s*"(\w+)"', text)
        outputs = re.findall(r'"output_tokens":\s*(\d+)', text)
        info.update(
            status=response.status, ms_total=int((time.monotonic() - started) * 1000),
            ms_first_byte=None if first_byte is None else int(first_byte * 1000),
            generation_id=generation.group(1) if generation else None,
            stop_reason=stops[-1] if stops else None, output_tokens=int(outputs[-1]) if outputs else None,
            blocks=sorted(set(re.findall(r'"content_block":\s*\{"type":\s*"(\w+)"', text))),
        )
        if response.status != 200:
            info["error_head"] = text[:300]
        self.server.log(info)

    def log_message(self, *args) -> None:
        pass


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, log_dir: Path, ignore: list[str]) -> None:
        super().__init__(("0.0.0.0", port), Handler)
        self.ignore, self.calls, self.lock = ignore, log_dir / "calls.jsonl", threading.Lock()
        log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, info: dict) -> None:
        with self.lock, self.calls.open("a") as handle:
            handle.write(json.dumps(info, sort_keys=True) + "\n")


def fetch(directory: Path) -> int:
    """Attach provider, finish reason and true cost to every logged call, from OpenRouter's generation records."""
    key = os.environ["OPENROUTER_API_KEY"]
    rows = [json.loads(line) for line in (directory / "calls.jsonl").read_text().splitlines() if line.strip()]
    keep = ("provider_name", "model", "finish_reason", "native_finish_reason", "tokens_prompt", "tokens_completion",
            "native_tokens_prompt", "native_tokens_completion", "native_tokens_cached", "native_tokens_reasoning",
            "total_cost", "cache_discount", "latency", "generation_time", "created_at")
    out, missing = [], 0
    for row in rows:
        gid, record = row.get("generation_id"), {}
        for attempt in range(6 if gid else 0):
            try:
                request = urllib.request.Request(
                    "https://openrouter.ai/api/v1/generation?id=" + gid, headers={"Authorization": "Bearer " + key})
                record = json.load(urllib.request.urlopen(request, timeout=30))["data"]
                break
            except urllib.error.HTTPError:
                time.sleep(2 + attempt * 2)  # the record can lag the response by a few seconds
        missing += bool(gid) and not record
        out.append({**row, "generation": {k: record.get(k) for k in keep} if record else None})
    (directory / "generations.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in out))
    print(f"generations: {len(out)} calls, {missing} without a generation record")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--log-dir", required=True)
    serve.add_argument("--ignore", default="StreamLake")
    sub.add_parser("fetch").add_argument("directory")
    args = parser.parse_args()
    if args.cmd == "fetch":
        return fetch(Path(args.directory))
    server = Server(args.port, Path(args.log_dir), [p for p in args.ignore.split(",") if p])
    print(f"proxy on :{args.port} ignoring {server.ignore}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
