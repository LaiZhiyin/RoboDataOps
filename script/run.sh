#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR"
export UV_CACHE_DIR="$PROJECT_DIR/.cache/uv"
exec uv run --frozen streamlit run app.py "$@"
