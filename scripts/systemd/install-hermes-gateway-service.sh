#!/usr/bin/env bash
# Install Hermes gateway as systemd unit (run as root on the Hermes host).
set -euo pipefail

UNIT_SRC="$(cd "$(dirname "$0")" && pwd)/hermes-gateway.service"
UNIT_DST="/etc/systemd/system/hermes-gateway.service"

if [[ ! -f "$UNIT_SRC" ]]; then
  echo "Missing $UNIT_SRC" >&2
  exit 1
fi

install -m 644 "$UNIT_SRC" "$UNIT_DST"
mkdir -p /root/.hermes/logs

systemctl daemon-reload
systemctl enable hermes-gateway.service

# Stop any manually-started gateway so the port is free
pkill -f "hermes_cli.main gateway" 2>/dev/null || true
sleep 2

systemctl restart hermes-gateway.service
systemctl --no-pager status hermes-gateway.service

echo ""
echo "Logs: journalctl -u hermes-gateway -f"
echo "     tail -f /root/.hermes/logs/gateway.log"
