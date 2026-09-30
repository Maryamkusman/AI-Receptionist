#!/usr/bin/env bash
# Start FullChair locally: API on :8000, dashboard on :3000.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d backend/.venv ]; then
  echo "→ Setting up the Python environment…"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q --upgrade pip
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi
[ -f backend/.env ] || cp backend/.env.example backend/.env

if [ ! -d dashboard/node_modules ]; then
  echo "→ Installing dashboard packages…"
  (cd dashboard && npm install --silent)
fi

echo "→ Starting API on http://localhost:8000"
# No --reload: file syncing (e.g. iCloud on ~/Documents) can trigger endless restarts.
(cd backend && .venv/bin/uvicorn app.main:app --port 8000) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT

cd dashboard
# Serve a production build: pages load instantly instead of compiling on first visit.
# After changing dashboard code, rebuild with: (cd dashboard && npm run build)
if [ ! -f .next/BUILD_ID ]; then
  echo "→ Building the dashboard (first run only, can take a few minutes)…"
  npm run build
fi
echo "→ Starting dashboard on http://localhost:3000"
npm start
