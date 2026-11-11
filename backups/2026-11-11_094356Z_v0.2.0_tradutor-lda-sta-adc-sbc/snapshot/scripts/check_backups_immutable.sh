#!/usr/bin/env bash
# check_backups_immutable.sh — falha se qualquer arquivo em backups/ foi
# modificado, renomeado ou apagado (apenas adições são permitidas).
# Também exige README.md em cada diretório de backup.
#
# Uso: scripts/check_backups_immutable.sh [<ref-base>]   (padrão: HEAD)
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
BASE="${1:-HEAD}"
rc=0

# 1) alterações não-"A" (added) em backups/ comparando árvore de trabalho com BASE
bad="$(git diff --name-status "$BASE" -- backups/ | grep -v '^A' || true)"
if [ -n "$bad" ]; then
  echo "VIOLAÇÃO: backups/ foi alterado (somente adição é permitida):" >&2
  echo "$bad" >&2; rc=1
fi

# 2) todo backup precisa de README.md
if [ -d backups ]; then
  for d in backups/*/; do
    [ -f "${d}README.md" ] || { echo "VIOLAÇÃO: ${d} sem README.md" >&2; rc=1; }
  done
fi

[ "$rc" -eq 0 ] && echo "OK: backups/ íntegro."
exit "$rc"
