#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$PROJECT_DIR"
if [[ -n "$(git status --porcelain)" ]]; then
    printf '%s\n' 'Source files have local changes. Commit or preserve them before updating.' >&2
    exit 1
fi
"$PROJECT_DIR/.venv/bin/python" scripts/backup.py
git pull --ff-only
"$PROJECT_DIR/.venv/bin/python" -m pip install -r requirements.txt
"$PROJECT_DIR/.venv/bin/python" -m unittest discover -s tests -q
sudo systemctl restart gitwatch.service
sudo systemctl status gitwatch.service --no-pager
