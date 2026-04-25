#!/usr/bin/env bash
# deploy-update.sh — One-command update for TrumpTrade on the VM.
# Run as the trumptrade user after a git push from your dev machine.
#
# Usage: bash scripts/deploy-update.sh

set -euo pipefail

REPO_DIR="/home/trumptrade/trumptrade"
VENV="$REPO_DIR/.venv"

echo "[1/5] Pulling latest code..."
cd "$REPO_DIR"
git pull origin main

echo "[2/5] Installing/updating Python dependencies..."
source "$VENV/bin/activate"
uv pip install -e . 2>/dev/null || pip install -e .

echo "[3/5] Running database migrations..."
alembic upgrade head

echo "[4/5] Rebuilding frontend..."
cd "$REPO_DIR/frontend"
npm install --prefer-offline
npm run build

echo "[5/5] Restarting systemd service..."
sudo systemctl restart trumptrade
sudo systemctl status trumptrade --no-pager -l

echo ""
echo "Deploy complete. Dashboard: http://$(curl -s ifconfig.me)"
