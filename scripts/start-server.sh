#!/usr/bin/env bash
# Clone-and-run for Linux. Creates repo-root .venv; never uses system pip.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pick_python() {
  local cmd
  for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
      if "$cmd" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"; then
        printf "%s" "$cmd"
        return 0
      fi
    fi
  done
  return 1
}

if ! command -v python3 >/dev/null 2>&1 && ! command -v python3.12 >/dev/null 2>&1 && ! command -v python3.11 >/dev/null 2>&1; then
  echo "python3 is required (3.11+)." >&2
  exit 1
fi

PY="$(pick_python)" || {
  echo "Python 3.11+ is required (python3 on PATH is too old)." >&2
  exit 1
}

VENV="$ROOT/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PY" -m venv "$VENV"
fi

"$VENV/bin/pip" install -q -U pip
"$VENV/bin/pip" install -q -r "$ROOT/api/requirements.txt"

if [[ ! -f "$ROOT/api/.env" ]]; then
  cp "$ROOT/api/.env.example" "$ROOT/api/.env"
fi

if grep -Eq '^ASR_BACKEND=allosaurus[[:space:]]*$' "$ROOT/api/.env"; then
  "$VENV/bin/pip" install -q -r "$ROOT/api/requirements-allosaurus.txt"
fi

cd "$ROOT/api"
exec "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port 18741
