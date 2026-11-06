#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$ROOT_DIR/frontend" && npm install)
fi

if [[ ! -d "$ROOT_DIR/backend/.venv" ]]; then
  echo "Creating backend virtual environment..."
  python3 -m venv "$ROOT_DIR/backend/.venv"
fi

echo "Installing backend dependencies..."
"$ROOT_DIR/backend/.venv/bin/pip" install -q -r "$ROOT_DIR/backend/requirements.txt"

if [[ ! -f "$ROOT_DIR/backend/.env" ]]; then
  cp "$ROOT_DIR/backend/.env.example" "$ROOT_DIR/backend/.env"
fi

cleanup() {
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd "$ROOT_DIR/backend" && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
(cd "$ROOT_DIR/frontend" && npm run dev -- --host 0.0.0.0) &

echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000/docs"
wait

