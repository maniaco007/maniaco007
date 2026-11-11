#!/usr/bin/env bash
# Compila os headers do runtime em C89 estrito, para os dois alvos lógicos de
# configuração, tratando avisos como erros. (Não substitui o armcc do SDK 3DO,
# que não está disponível aqui: valida portabilidade/C89 e consistência.)
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
CC="${CC:-gcc}"
FLAGS="-std=c89 -pedantic -Wall -Wextra -Werror -fsyntax-only -I$HERE/runtime/include"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

for h in "$HERE"/runtime/include/lynx/*.h; do
  # cada header precisa ser autossuficiente (compilar sozinho)
  printf '#include "lynx/%s"\ntypedef int lx_tu_nonempty;\n' "$(basename "$h")" > "$TMP/one.c"
  $CC $FLAGS "$TMP/one.c"
done
$CC $FLAGS -DLX_TARGET_HOST "$HERE/runtime/tests/header_check.c"
$CC $FLAGS -DLX_TARGET_3DO  "$HERE/runtime/tests/header_check.c"
echo "OK: headers compilam em C89 (host + 3DO config)."
