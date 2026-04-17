#!/usr/bin/env python3
"""
Minimal two-user workspace isolation test (Lumii session_id → api_workspaces/lumii_users/).

Prereqs: Hermes API Server listening (e.g. API_SERVER_ENABLED=true), same auth as production.

  export HERMES_URL=http://127.0.0.1:8642
  export HERMES_API_KEY=<same as API_SERVER_KEY on Hermes, if set>

  python3 scripts/lumii_two_user_workspace_test.py

Flow:
  1) session_id=lumii:myapp:alice:c1 → ask agent to write notes.txt in workspace
  2) session_id=lumii:myapp:bob:c1   → ask agent to list current directory

On the Hermes host, expect:
  $HERMES_HOME/api_workspaces/lumii_users/myapp_alice/notes.txt  exists
  $HERMES_HOME/api_workspaces/lumii_users/myapp_bob/            no notes.txt (bob listing should not show alice file)

Important: ``HERMES_HOME`` is whatever the **gateway process** has in its environment (see systemd unit or
``docker inspect``). Profile mode uses e.g. ``~/.hermes/profiles/<name>`` — then workspaces live under
that profile dir, **not** necessarily ``~/.hermes/api_workspaces/...``.

If ``cat .../myapp_alice/notes.txt`` says missing but the run reported success, check SSE ``tool.completed``
for ``write_file`` — the model may have answered without calling the tool.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Iterator, Tuple


def _env(name: str, default: str) -> str:
    v = os.environ.get(name, "").strip()
    return v if v else default


HERMES_URL = _env("HERMES_URL", "http://127.0.0.1:8642").rstrip("/")
API_KEY = _env("HERMES_API_KEY", "")
SSE_READ_TIMEOUT = int(_env("HERMES_SSE_READ_TIMEOUT", "600"))


def _request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int | float | None = None,
) -> Any:
    h = dict(headers or {})
    if data is not None and "Content-Type" not in h:
        h["Content-Type"] = "application/json"
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    ctx = ssl.create_default_context()
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def post_run(user_message: str, session_id: str) -> str:
    url = f"{HERMES_URL}/v1/runs"
    body = json.dumps({"input": user_message, "session_id": session_id}, ensure_ascii=False).encode("utf-8")
    try:
        with _request(url, method="POST", data=body, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} failed: {e.code} {e.reason}\n{detail}") from e
    data = json.loads(raw)
    rid = data.get("run_id")
    if not rid:
        raise RuntimeError(f"Unexpected response (no run_id): {raw}")
    return str(rid)


def _iter_sse_json(resp: Any) -> Iterator[dict[str, Any]]:
    buf = ""
    while True:
        chunk = resp.read(8192)
        if not chunk:
            break
        buf += chunk.decode("utf-8", errors="replace")
        while "\n\n" in buf:
            block, buf = buf.split("\n\n", 1)
            for line in block.split("\n"):
                line = line.strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    yield json.loads(line[6:])


def wait_run_completed(run_id: str) -> Tuple[dict, list[str]]:
    """Return (final run.completed payload, list of tool names from tool.completed events)."""
    url = f"{HERMES_URL}/v1/runs/{run_id}/events"
    tools_completed: list[str] = []
    try:
        with _request(url, timeout=SSE_READ_TIMEOUT) as resp:
            for ev in _iter_sse_json(resp):
                et = ev.get("event")
                if et == "tool.completed":
                    t = ev.get("tool")
                    if t:
                        tools_completed.append(str(t))
                if et == "run.completed":
                    return ev, tools_completed
                if et == "run.failed":
                    raise RuntimeError(f"run.failed: {ev}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {url} failed: {e.code} {e.reason}\n{detail}") from e
    raise RuntimeError("SSE ended without run.completed / run.failed")


def main() -> int:
    alice = "lumii:myapp:alice:c1"
    bob = "lumii:myapp:bob:c1"

    print("HERMES_URL =", HERMES_URL)
    print("--- Run 1: alice → write notes.txt (must use write_file tool) ---")
    r1 = post_run(
        "You MUST use the write_file tool (do not claim success in text only). "
        "Write path: notes.txt (relative path). "
        "Content must be exactly one line: hello-from-alice",
        alice,
    )
    print("run_id:", r1)
    out1, tools1 = wait_run_completed(r1)
    print("run.completed; output preview:", str(out1.get("output", ""))[:400])
    print("tools completed (SSE):", tools1)
    if "write_file" not in tools1:
        print(
            "WARNING: no write_file in tool.completed — the model may have hallucinated; "
            "on-disk notes.txt may be missing. Re-run or switch model.",
        )

    print("--- Run 2: bob → list directory ---")
    r2 = post_run(
        "List the files and subdirectories in the current workspace directory only "
        "(use your file or terminal tools). Report the names you see.",
        bob,
    )
    print("run_id:", r2)
    out2, tools2 = wait_run_completed(r2)
    print("run.completed; output preview:", str(out2.get("output", ""))[:400])
    print("tools completed (SSE):", tools2)

    print()
    print("On-disk layout (HERMES_HOME = gateway process env, not always ~/.hermes):")
    print("  $HERMES_HOME/api_workspaces/lumii_users/myapp_alice/notes.txt   ← expect file if write_file ran")
    print("  $HERMES_HOME/api_workspaces/lumii_users/myapp_bob/              ← no notes.txt from alice")
    print()
    print("If unsure where HERMES_HOME is, on the server run:")
    print("  find /root -path '*/api_workspaces/lumii_users/myapp_alice/*' 2>/dev/null | head -20")
    print("or check the service: grep -r HERMES_HOME /etc/systemd/system/*.service ~/.config/systemd/user/*.service 2>/dev/null")
    print()
    print("Quick check (replace HERMES_HOME after you resolve it):")
    print("  ls -la \"$HERMES_HOME/api_workspaces/lumii_users/myapp_alice/\"")
    print("  ls -la \"$HERMES_HOME/api_workspaces/lumii_users/myapp_bob/\"")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
