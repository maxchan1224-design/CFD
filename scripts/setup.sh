#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
(cd frontend && npm ci && npm run build)
# Debian signatures remain enabled. This build only uses Debian's package mirrors.
docker --host=unix:///var/run/docker.sock build -f Dockerfile.foam -t demo-kitchen-openfoam:1912 .
