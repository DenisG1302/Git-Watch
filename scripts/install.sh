#!/usr/bin/env bash
set -euo pipefail
# Usage: sudo bash scripts/install.sh [LAN_IP] [SERVICE_USER] [PROXY_CONFIG]
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
BIND_IP="${1:-127.0.0.1}"
SERVICE_USER="${2:-${SUDO_USER:-$(id -un)}}"
PROXY_SOURCE="${3:-}"
if [[ "$EUID" -ne 0 ]]; then printf '%s\n' 'Run with sudo.' >&2; exit 1; fi
case "$PROJECT_DIR" in *[!a-zA-Z0-9_./-]*) printf '%s\n' 'Install into a path without spaces or special characters.' >&2; exit 1;; esac
id "$SERVICE_USER" >/dev/null
python3 - "$BIND_IP" <<'PY'
import ipaddress,sys
ip=ipaddress.ip_address(sys.argv[1])
if ip.version!=4 or not ip.is_private or ip.is_unspecified:
    raise SystemExit('Use a specific private IPv4 address or 127.0.0.1')
PY
install -d -m 700 -o "$SERVICE_USER" -g "$(id -gn "$SERVICE_USER")" "$PROJECT_DIR/data"
if [[ -n "$PROXY_SOURCE" ]]; then
    python3 - "$PROXY_SOURCE" "$PROJECT_DIR/data/telegram-proxy.json" <<'PY'
import json,os,sys
from pathlib import Path
source=json.loads(Path(sys.argv[1]).read_text())
proxy=source.get('telegram',{}).get('proxies')
if not isinstance(proxy,dict) or not proxy.get('https'):
    raise SystemExit('The source has no Telegram HTTPS proxy; nothing was changed.')
target=Path(sys.argv[2])
temporary=target.with_suffix('.tmp')
with open(temporary,'w',encoding='utf-8') as f:
    os.chmod(temporary,0o600)
    json.dump(proxy,f)
os.replace(temporary,target)
print('Telegram proxy imported; credentials are not displayed.')
PY
    chown "$SERVICE_USER:$(id -gn "$SERVICE_USER")" "$PROJECT_DIR/data/telegram-proxy.json"
fi
if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    runuser -u "$SERVICE_USER" -- python3 -m venv "$PROJECT_DIR/.venv"
fi
runuser -u "$SERVICE_USER" -- "$PROJECT_DIR/.venv/bin/python" -m pip install -r "$PROJECT_DIR/requirements.txt"
runuser -u "$SERVICE_USER" -- bash -c 'cd "$1" && "$1/.venv/bin/python" -m unittest discover -s tests -q' _ "$PROJECT_DIR"
cat > /etc/systemd/system/gitwatch.service <<EOF
[Unit]
Description=Git Watch - GitHub monitoring and Telegram notifications
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$SERVICE_USER
Group=$(id -gn "$SERVICE_USER")
WorkingDirectory=$PROJECT_DIR
Environment=GITWATCH_HOST=$BIND_IP
Environment=GITWATCH_PORT=8788
Environment=GITWATCH_TRUSTED_HOSTS=$BIND_IP,127.0.0.1,localhost
Environment=GITWATCH_DATA=$PROJECT_DIR/data
Environment=PYTHONUNBUFFERED=1
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/run.py
Restart=always
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$PROJECT_DIR/data

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now gitwatch.service
systemctl restart gitwatch.service
printf 'Git Watch: http://%s:8788/\n' "$BIND_IP"
