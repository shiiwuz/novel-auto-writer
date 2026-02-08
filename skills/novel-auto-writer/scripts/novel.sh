#!/usr/bin/env bash
set -euo pipefail

# Wrapper for the local novel-writer CLI.
# Ensures we run from the right directory and load the repo-local .env.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT/projects/novel-writer-cli"

set -a
# shellcheck disable=SC1091
. ./.env
set +a

python3 -m novel_writer "$@"
