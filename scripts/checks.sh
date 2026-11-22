#!/usr/bin/env bash
# The complete check suite. CI runs this file directly; scripts/test.sh runs it in Docker.
#
#   scripts/checks.sh                 lint, types, privacy, all tests with coverage
#   scripts/checks.sh tests/test_x.py only the given pytest arguments
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$#" -gt 0 ]; then
    exec python -m pytest "$@"
fi

echo "== ruff check" && ruff check .
echo "== ruff format" && ruff format --check .
echo "== mypy" && mypy
echo "== privacy" && python scripts/check_privacy.py
echo "== pytest" && python -m pytest --cov --cov-report=term-missing
