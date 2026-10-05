#!/bin/bash
# Run all code quality checks without modifying files (suitable for CI).
set -e
cd "$(dirname "$0")/.."

echo "Checking formatting with black..."
uv run black --check --diff .

echo "All quality checks passed."
