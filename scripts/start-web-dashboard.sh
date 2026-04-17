#!/usr/bin/env bash
# 启动 Hermes Web 控制台，默认 http://127.0.0.1:9119/
# 依赖：pip install 'hermes-agent[web]'；首次运行会在 web/ 下执行 npm install && npm run build。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if command -v uv >/dev/null 2>&1; then
  exec uv run --directory "$ROOT" python -m hermes_cli.main dashboard --host 127.0.0.1 --port 9119 "$@"
fi

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" -m hermes_cli.main dashboard --host 127.0.0.1 --port 9119 "$@"
fi

exec python3 -m hermes_cli.main dashboard --host 127.0.0.1 --port 9119 "$@"
