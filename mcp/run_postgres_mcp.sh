#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
CURRENT_DIR="$(pwd -P)"

if [[ "$CURRENT_DIR" != "$PROJECT_ROOT" ]]; then
  echo "MCP PostgreSQL доступен только из KateFitNotes_telegram." >&2
  exit 1
fi

exec npx -y @microsoft/postgres-mcp run --no-telemetry
