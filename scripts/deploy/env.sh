#!/usr/bin/env bash
# Shared .env access for the scalar image references and node IDs managed by
# deployment scripts. Never source an environment file as shell code.

read_env_value() {
  local key="$1" env_file="${2:-.env}"
  [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || return 2
  awk -v key="$key" '
    $0 ~ ("^[[:space:]]*(export[[:space:]]+)?" key "[[:space:]]*=") {
      value = $0
      sub(/^[^=]*=[[:space:]]*/, "", value)
      sub(/[[:space:]]+$/, "", value)
      quote = substr(value, 1, 1)
      if (quote == "\"" || quote == sprintf("%c", 39)) {
        value = substr(value, 2)
        end = index(value, quote)
        if (end) value = substr(value, 1, end - 1)
      } else {
        sub(/[[:space:]]+#.*$/, "", value)
        sub(/[[:space:]]+$/, "", value)
      }
    }
    END { print value }
  ' "$env_file"
}
