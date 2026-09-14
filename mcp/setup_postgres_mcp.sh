#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  echo "Не найден .env в корне репозитория." >&2
  exit 1
fi

read_env_value() {
  local name="$1"
  local value

  value="$(awk -v key="$name" '
    index($0, key "=") == 1 {
      print substr($0, length(key) + 2)
      exit
    }
  ' .env)"

  if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then
    value="${value:1:${#value}-2}"
  fi

  printf '%s' "$value"
}

MCP_DB_USER="$(read_env_value MCP_DB_USER)"
MCP_DB_PASSWORD="$(read_env_value MCP_DB_PASSWORD)"

if [[ -z "$MCP_DB_USER" ]]; then
  echo "В .env не задан MCP_DB_USER." >&2
  exit 1
fi

if [[ -z "$MCP_DB_PASSWORD" ]]; then
  echo "В .env не задан MCP_DB_PASSWORD." >&2
  exit 1
fi

MCP_PROFILE="$(read_env_value MCP_DB_PROFILE)"
MCP_HOST="$(read_env_value MCP_DB_HOST)"
MCP_PORT="$(read_env_value MCP_DB_PORT)"
MCP_DATABASE="$(read_env_value MCP_DB_DATABASE)"

MCP_PROFILE="${MCP_PROFILE:-kate_fit_notes_readonly}"
MCP_HOST="${MCP_HOST:-localhost}"
MCP_PORT="${MCP_PORT:-5432}"
MCP_DATABASE="${MCP_DATABASE:-Kate_fitness}"

npx -y @microsoft/postgres-mcp connection add "$MCP_PROFILE" \
  "host=$MCP_HOST port=$MCP_PORT user=$MCP_DB_USER dbname=$MCP_DATABASE" \
  --access-mode ro
POSTGRES_MCP_PASSWORD="$MCP_DB_PASSWORD" \
  npx -y @microsoft/postgres-mcp connection set-password "$MCP_PROFILE"
npx -y @microsoft/postgres-mcp connection list
