#!/usr/bin/env bash
# Teste diferencial: lynx2c -> C89 -> gcc (host)  vs.  núcleo de referência (lynxtrace).
# Compila o C gerado com -std=c89 -pedantic -Wall -Wextra -Werror em -O0 e -O2.
# Uso: pc-tools/tests/run_diff.sh [outdir]      (padrão: <projeto>/build/test)
# SKIP_UNIT=1 pula os unitários; SKIP_BLOCKS=1 pula o corpus de blocos retos; LX_LITE=1 pula o corpus
# EXAUSTIVO de imediatos; OPTS="-O0" compila só em -O0 (modos rápidos para teste de mutação).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$PROJ/build/test}"
CC="${CC:-gcc}"
export PYTHONPATH="$PROJ/pc-tools/lynx2c:$PROJ/pc-tools/lynxtrace:$PROJ/pc-tools/tests${PYTHONPATH:+:$PYTHONPATH}"

if [ -z "${SKIP_UNIT:-}" ]; then   # SKIP_UNIT=1: isola o teste diferencial (usado em teste de mutação)
  echo "== 1/4 testes unitários Python"
  python3 -m unittest discover -s "$HERE" -p 'test_*.py' 2>&1 | tail -4
fi

echo "== 2/4 gerando corpus em $OUT"
mkdir -p "$OUT"
if [ -z "${SKIP_BLOCKS:-}" ]; then python3 "$HERE/gen_vectors.py" "$OUT"; fi
python3 "$HERE/gen_programs.py" "$OUT"

echo "== 3/4 compilando (C89 estrito, -Werror)"
INC="-I$PROJ/runtime/include"
STRICT="-std=c89 -pedantic -Wall -Wextra -Werror"
for O in ${OPTS:--O0 -O2}; do
  $CC $STRICT $O $INC -c "$PROJ/runtime/src/lx_mem.c" -o "$OUT/lx_mem$O.o"
  $CC $STRICT $O $INC -c "$PROJ/runtime/src/lx_alu.c" -o "$OUT/lx_alu$O.o"
  $CC $STRICT $O $INC -c "$HERE/harness/lx_test_stubs.c" -o "$OUT/stubs$O.o"
  if [ -z "${SKIP_BLOCKS:-}" ]; then
    $CC $STRICT $O $INC -c "$OUT/tests_gen.c" -o "$OUT/tests_gen$O.o"
    $CC $STRICT $O $INC -c "$HERE/harness/main.c" -o "$OUT/main$O.o"
    $CC $O "$OUT/tests_gen$O.o" "$OUT/lx_mem$O.o" "$OUT/lx_alu$O.o" "$OUT/stubs$O.o" "$OUT/main$O.o" -o "$OUT/harness$O"
  fi
  # programas com fluxo de controle: trampolim REAL (lx_dispatch/lx_overlay)
  $CC $STRICT $O $INC -c "$OUT/progs_gen.c" -o "$OUT/progs_gen$O.o"
  $CC $STRICT $O $INC -c "$PROJ/runtime/src/lx_dispatch.c" -o "$OUT/lx_dispatch$O.o"
  $CC $STRICT $O $INC -c "$PROJ/runtime/src/lx_overlay.c" -o "$OUT/lx_overlay$O.o"
  $CC $STRICT $O $INC -c "$HERE/harness/main_prog.c" -o "$OUT/main_prog$O.o"
  $CC $O "$OUT/progs_gen$O.o" "$OUT/lx_mem$O.o" "$OUT/lx_dispatch$O.o" "$OUT/lx_overlay$O.o" \
      "$OUT/lx_alu$O.o" "$OUT/stubs$O.o" "$OUT/main_prog$O.o" -o "$OUT/harness_prog$O"
done

echo "== 4/4 executando vetores"
rc=0
for O in ${OPTS:--O0 -O2}; do
  # vigia: um runtime defeituoso (ex.: ciclos que não avançam) faria os laços do corpus nunca terminarem
  [ -z "${SKIP_BLOCKS:-}" ] && { echo "-- $O (blocos retos)"; timeout "${HARNESS_TIMEOUT:-300}" "$OUT/harness$O" "$OUT/vectors.bin" || { rc=$?; [ $rc -eq 124 ] && echo "TEMPO ESGOTADO (possível não-terminação)"; }; }
  echo "-- $O (programas)";      timeout "${HARNESS_TIMEOUT:-300}" "$OUT/harness_prog$O" "$OUT/programs.bin" || { rc=$?; [ $rc -eq 124 ] && echo "TEMPO ESGOTADO (possível não-terminação)"; }
done
exit $rc
