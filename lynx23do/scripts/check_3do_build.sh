#!/usr/bin/env bash
# Verificação ESTÁTICA do que vai para o 3DO — roda no PC, sem executar o armcc nem nada do devkit.
#   1) todo o runtime + o jogo gerado compilam como ARM BIG-ENDIAN em C89 estrito (clang, -Werror);
#   2) se DEVKIT apontar para o trapexit/3do-devkit: o backend 3DO é analisado contra os headers REAIS do SDK
#      (declaração implícita, ponteiros incompatíveis, campos inexistentes viram erro).
# Limites: clang não é o armcc (a aceitação final é do armcc do SDK) e nada disto executa em emulador/hardware.
# Uso: [DEVKIT=/caminho/3do-devkit] scripts/check_3do_build.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
RT="$HERE/runtime"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export PYTHONPATH="$HERE/pc-tools/lynx2c"

echo "== gerando o demo (BS93 -> C traduzido)"
python3 "$HERE/games/demo_bars/demo.py" "$TMP/demo.o" >/dev/null
python3 -m lynx2c build --file "$TMP/demo.o" --name demo --out-dir "$TMP" >/dev/null

# libc: com o devkit usa o string.h do SDK (como o build real); sem ele, um stub mínimo
mkdir -p "$TMP/stub"
printf 'typedef unsigned int size_t;\nvoid *memcpy(void *, const void *, size_t);\nvoid *memset(void *, int, size_t);\n' > "$TMP/stub/string.h"
LIBC="-I$TMP/stub"
[ -n "${DEVKIT:-}" ] && [ -d "$DEVKIT/include/3do" ] && LIBC="-I$DEVKIT/include/3do"
ARM="--target=armeb-none-eabi -mcpu=arm7tdmi -marm -ffreestanding -std=c89 -pedantic -Wall -Wextra -Werror -DLX_TARGET_3DO=1 -I$RT/include $LIBC"
echo "== runtime + jogo como ARM big-endian, C89 estrito"
for f in lx_mem lx_dispatch lx_overlay lx_alu lx_video lx_mikey lx_suzy_min lx_machine; do
  clang $ARM -Os -c "$RT/src/$f.c" -o "$TMP/$f.o"
done
clang $ARM -Os -c "$TMP/demo_gen.c" -o "$TMP/demo_gen.o"
clang $ARM -Os -c "$TMP/demo_image.c" -o "$TMP/demo_image.o"
llvm-size "$TMP"/demo_gen.o "$TMP"/lx_machine.o | sed 's/^/   /'

if [ -n "${DEVKIT:-}" ]; then
  SDK="$DEVKIT/include/3do"
  [ -d "$SDK" ] || { echo "DEVKIT sem include/3do: $DEVKIT" >&2; exit 2; }
  echo "== backend 3DO contra os headers reais do SDK ($SDK)"
  for f in lx_platform_3do lx_main_3do; do
    clang --target=arm-none-eabi -ffreestanding -fsyntax-only -std=gnu89 -D'__swi(x)=' -D'__value_in_regs=' \
      -DLX_TARGET_3DO=1 -D__3DO__=1 -Wno-everything -Werror=implicit-function-declaration \
      -Werror=incompatible-pointer-types -Werror=int-conversion -Werror=return-type \
      -I "$SDK" -I "$RT/include" "$RT/platform/3do/$f.c"
    echo "   ok $f.c"
  done
else
  echo "== (DEVKIT não definido: pulando a checagem do backend contra os headers do SDK)"
fi
echo "OK: verificação estática do build 3DO."
