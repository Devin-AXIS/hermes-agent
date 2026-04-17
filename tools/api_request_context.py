"""Thread-local flags for Hermes API Server agent runs.

``gateway/run.py`` sets ``HERMES_EXEC_ASK=1`` process-wide so messaging platforms
can prompt for dangerous commands.  HTTP ``/v1/runs`` and chat completions have no
approval UI — without this marker, :func:`tools.approval.check_all_command_guards`
falls through to ``approval_required`` and every Tirith-flagged terminal command
fails while the agent cannot recover.

Set :func:`set_api_server_agent_thread` around ``run_conversation`` in
``gateway/platforms/api_server.py`` only.
"""

from __future__ import annotations

import threading

_tls = threading.local()


def set_api_server_agent_thread(active: bool) -> None:
    _tls.api_server_agent = bool(active)


def is_api_server_agent_thread() -> bool:
    return bool(getattr(_tls, "api_server_agent", False))
