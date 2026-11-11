#!/usr/bin/env bash
# Suítes funcionais INDEPENDENTES de Klaus Dormann (GPL-3.0; github.com/Klaus2m5/6502_65C02_functional_tests)
# executadas pelo pipeline completo: lynx2c -> C89 -> gcc -> lx_run, com sementes iterativas.
#
# As imagens são baixadas para build/dormann/ (ignorado pelo git; NÃO são redistribuídas aqui) e conferidas por
# SHA-256. As imagens são tratadas apenas como BYTES. Sem rede, o script avisa e sai com código 77 (pulado).
#
# Trechos DISPENSADOS por hook HLE (política "hook" do docs/02 §6) — só o que o CPU do Lynx não tem ou exige
# alvo de desvio dinâmico:
#   6502:  $0446 -> $0581  teste de faixa de desvio (reescreve o operando de um Bcc: SMC de operando de desvio)
#   65C02: $071C,$0B94     BBR/BBS (Rockwell)           $0C04  NOPs indefinidos de 1/2/3 bytes
#          $1E69           RMB/SMB (Rockwell)
# SMC de operando IMEDIATO (instruções montadas na RAM) é tratado de verdade por --smc-operand.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$HERE/../../.." && pwd)"
DL="$PROJ/build/dormann"
BASE="https://raw.githubusercontent.com/Klaus2m5/6502_65C02_functional_tests/master/bin_files"
T6502="6502_functional_test.bin";           H6502="fa12bfc761e6f9057e4cc01a665a7b800ff01ae91f598af1e39a1201d01953fd"
T65C02="65C02_extended_opcodes_test.bin";   H65C02="10a2a07fa240666fa610c46accebe8d42b1000feef3aae619da15a8d152869b2"
mkdir -p "$DL"

fetch() {  # nome sha256
  if [ ! -f "$DL/$1" ]; then
    curl -fsS -m 60 -o "$DL/$1.part" "$BASE/$1" || { echo "sem rede/acesso: não foi possível baixar $1 (pulado)"; exit 77; }
    mv "$DL/$1.part" "$DL/$1"
  fi
  echo "$2  $DL/$1" | sha256sum -c --quiet - || { echo "SHA-256 inesperado para $1 (a suíte mudou upstream?)" >&2; exit 2; }
}
fetch "$T6502" "$H6502"
fetch "$T65C02" "$H65C02"

export PYTHONPATH="$PROJ/pc-tools/lynx2c${PYTHONPATH:+:$PYTHONPATH}"
rc=0
echo "== Dormann 6502_functional_test (NMOS: todos os opcodes documentados, modos, flags, decimal, BRK/RTI, I)"
python3 "$HERE/run_functional.py" "$DL/$T6502" --entry 0x0400 --success 0x3469 --workdir "$PROJ/build/functional" \
  --smc-operand 0x0209 --smc-operand 0x020C --smc-operand 0x020F --smc-operand 0x0212 --smc-operand 0x0215 \
  --skip 0x0446:0x0581 || rc=$?
echo "== Dormann 65C02_extended_opcodes_test (65C02: BRA STZ TSB TRB PHX.. INC A BIT# (zp) JMP(abs,X) decimal 65C02)"
python3 "$HERE/run_functional.py" "$DL/$T65C02" --entry 0x0400 --success 0x24F1 --workdir "$PROJ/build/functional_c02" \
  --smc-operand 0x020B --smc-operand 0x020E \
  --skip 0x071C:0x0B88 --skip 0x0B94:0x0BF8 --skip 0x0C04:0x1654 --skip 0x1E69:0x222A || rc=$?
exit $rc
