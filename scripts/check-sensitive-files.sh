#!/usr/bin/env bash
set -euo pipefail

for file in "$@"; do
  case "$file" in
    .env|.env.*)
      if [[ "$file" == ".env.example" ]]; then
        continue
      fi
      printf 'Arquivo potencialmente sensível bloqueado: %s\n' "$file" >&2
      exit 1
      ;;
    *.pem|*.key|*credentials*|*service-account*.json)
      printf 'Arquivo potencialmente sensível bloqueado: %s\n' "$file" >&2
      exit 1
      ;;
  esac
done
