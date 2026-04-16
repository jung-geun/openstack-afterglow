#!/usr/bin/env bash
# CI 및 로컬에서 세 파일의 version 일치를 검증한다.
# node 없이 bash + grep + sed 만으로 동작하므로 self-hosted linux runner에서도 사용 가능.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

extract_pkg_version() {
    grep -m1 '"version"' "$1" | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/'
}

ROOT_V=$(extract_pkg_version "${ROOT_DIR}/package.json")
FE_V=$(extract_pkg_version "${ROOT_DIR}/frontend/package.json")
BE_V=$(grep -E '^version[[:space:]]*=' "${ROOT_DIR}/backend/pyproject.toml" \
    | head -1 | sed -E 's/.*"([^"]+)".*/\1/')

if [ "$ROOT_V" != "$FE_V" ] || [ "$ROOT_V" != "$BE_V" ]; then
    echo "✗ version mismatch:" >&2
    echo "  root package.json        : $ROOT_V" >&2
    echo "  frontend/package.json    : $FE_V" >&2
    echo "  backend/pyproject.toml   : $BE_V" >&2
    echo "" >&2
    echo "  fix: npm run version:sync" >&2
    exit 1
fi

# GitHub Actions tag push 이벤트에서는 git ref 와도 비교
GITHUB_REF="${GITHUB_REF:-}"
if [[ "$GITHUB_REF" == refs/tags/v* ]]; then
    TAG_V="${GITHUB_REF#refs/tags/v}"
    if [ "$TAG_V" != "$ROOT_V" ]; then
        echo "✗ git tag v$TAG_V ≠ package.json $ROOT_V" >&2
        echo "  태그 푸시 전에 npm version <level> 으로 먼저 bump 하세요" >&2
        exit 1
    fi
fi

echo "✓ all versions aligned: $ROOT_V"
