#!/bin/bash
# Auto-format the Python codebase with black.
set -e
cd "$(dirname "$0")/.."

echo "Formatting with black..."
uv run black .
