#!/usr/bin/env bash
# Run scripts/checks.sh inside the Docker test image (builds it on first use).
# All arguments are passed through to scripts/checks.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

TAG="$(cat "$ROOT/requirements_test.txt" "$ROOT/scripts/Dockerfile.test" | sha256sum | cut -c1-12)"
IMAGE="ha-petwalk-local-test:$TAG"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker build -t "$IMAGE" -f "$ROOT/scripts/Dockerfile.test" "$ROOT"
fi

# Git Bash on Windows rewrites POSIX paths; hand Docker a native path instead.
MOUNT="$ROOT"
if pwd -W >/dev/null 2>&1; then
    MOUNT="$(cd "$ROOT" && pwd -W)"
fi

MSYS_NO_PATHCONV=1 docker run --rm -v "$MOUNT:/src" "$IMAGE" bash scripts/checks.sh "$@"
