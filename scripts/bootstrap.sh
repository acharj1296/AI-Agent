# bootstrap.sh - Create venv, install dev deps, copy .env.example (Unix/macOS)
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install from https://docs.astral.sh/uv/ and re-run."
  exit 1
fi

uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example - review MONGODB_URI and other settings."
fi

echo "Setup complete. Activate: source .venv/bin/activate"