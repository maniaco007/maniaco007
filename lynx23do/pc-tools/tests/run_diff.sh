#!/usr/bin/env bash
# Teste diferencial: lynx2c -> C89 -> gcc (host)  vs.  núcleo de referência (lynxtrace).
# Compila o C gerado com -std=c89 -pedantic -Wall -Wextra -Werror em -O0 e -O2.
# Uso: pc-tools/tests/run_diff.sh [outdir]      (padrão: <projeto>/build/test)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$PROJ/build/test}"
CC="${CC:-gcc}"
export PYTHONPATH="$PROJ/pc-tools/lynx2c:$PROJ/pc-tools/lynxtrace${PYTHONPATH:+:$PYTHONPATH}"

if [ -z "${SKIP_UNIT:-}" ]; then   # SKIP_UNIT=1: isola o teste diferencial (usado em teste de mutação)
  echo "== 1/4 testes unitários Python"
  python3 -m unittest discover -s "$HERE" -p 'test_*.py' 2>&1 | tail -4
fi

echo "== 2/4 gerando corpus em $OUT"
python3 "$HERE/gen_vectors.py" "$OUT"

echo "== 3/4 compilando (C89 estrito, -Werror)"
INC="-I$PROJ/runtime/include"
STRICT="-std=c89 -pedantic -Wall -Wextra -Werror"
for O in -O0 -O2; do
  $CC $STRICT $O $INC -c "$OUT/tests_gen.c" -o "$OUT/tests_gen$O.o"
  $CC $STRICT $O $INC -c "$PROJ/runtime/src/lx_mem.c" -o "$OUT/lx_mem$O.o"
  $CC $STRICT $O $INC -c "$HERE/harness/lx_test_stubs.c" -o "$OUT/stubs$O.o"
  # main.c usa stdio/malloc: C89 também, sem -pedantic de tamanho de linha
  $CC $STRICT $O $INC -c "$HERE/harness/main.c" -o "$OUT/main$O.o"
  $CC $O "$OUT/tests_gen$O.o" "$OUT/lx_mem$O.o" "$OUT/stubs$O.o" "$OUT/main$O.o" -o "$OUT/harness$O"
done

echo "== 4/4 executando vetores"
rc=0
for O in -O0 -O2; do
  echo "-- $O"; "$OUT/harness$O" "$OUT/vectors.bin" || rc=$?
done
exit $rc
