"""
Thread-local workspace root for Hermes API Server multi-tenant runs.

When set (see gateway/platforms/api_server.py ``_run_agent``), file and terminal
tools must only read/write under this directory so concurrent Lumii users sharing
one gateway process do not touch each other's files.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

_thread_workspace_root = threading.local()


@contextmanager
def api_server_workspace_scope(root: Optional[Path]) -> Iterator[None]:
    """Bind a per-request workspace root for the current worker thread."""
    prev = getattr(_thread_workspace_root, "path", None)
    try:
        if root is None:
            if hasattr(_thread_workspace_root, "path"):
                delattr(_thread_workspace_root, "path")
        else:
            r = Path(root).resolve()
            r.mkdir(parents=True, exist_ok=True)
            _thread_workspace_root.path = r
        yield
    finally:
        if prev is None:
            if hasattr(_thread_workspace_root, "path"):
                delattr(_thread_workspace_root, "path")
        else:
            _thread_workspace_root.path = prev


def get_api_server_workspace_root() -> Optional[Path]:
    """Return the active workspace root for this thread, or None if unset."""
    return getattr(_thread_workspace_root, "path", None)
