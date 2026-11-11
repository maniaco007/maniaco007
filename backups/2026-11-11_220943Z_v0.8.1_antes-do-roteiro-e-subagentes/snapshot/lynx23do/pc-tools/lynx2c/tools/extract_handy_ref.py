"""Extrai de c65c02.h (emulador Handy) uma tabela de FATOS por opcode — mnemônico da operação e ciclos-base —
para servir de referência INDEPENDENTE do optable.json. Nenhum código do Handy é copiado para o repositório:
só o dado derivado (opcode -> N de ciclos de barramento, nome da operação, se é ilegal) em data/handy_reference.json.

Handy conta cada opcode como  gSystemCycleCount += 1 + N * CPU_RDWR_CYC  ->  ciclos do datasheet c = N + 1.
O Handy NÃO modela penalidade de cruzamento de página, o +1 do desvio tomado nem o +1 do modo decimal.

Uso: python3 tools/extract_handy_ref.py <c65c02.h>
     (baixe de https://raw.githubusercontent.com/libretro/libretro-handy/master/lynx/c65c02.h)
"""
import hashlib
import json
import os
import re
import sys

ADDR_MACROS = {"IMMEDIATE", "ABSOLUTE", "ZEROPAGE", "ZEROPAGE_X", "ZEROPAGE_Y", "ABSOLUTE_X", "ABSOLUTE_Y",
               "INDIRECT_ABSOLUTE_X", "RELATIVE", "INDIRECT_X", "INDIRECT_Y", "INDIRECT_ABSOLUTE", "INDIRECT"}


def extract(path):
    raw = open(path, "rb").read()
    src = raw.decode("latin-1")
    body = src[src.index("case 0x00:"):]
    parts = re.split(r"\n\s*case 0x([0-9A-Fa-f]{2}):", "\n" + body)
    table = {}
    for i in range(1, len(parts) - 1, 2):
        op = int(parts[i], 16)
        if op in table:
            break                                  # fim do switch principal
        blk = parts[i + 1].split("break;")[0]
        m = re.search(r"gSystemCycleCount\+=\(1\+\((\d+)\*CPU_RDWR_CYC\)\)", blk)
        macros = re.findall(r"\bx([A-Z0-9_]+)\(\)", blk)
        ops = [x for x in macros if x not in ADDR_MACROS]
        table["%02X" % op] = {"n": int(m.group(1)) if m else None, "op": ops[0] if ops else None}
    assert len(table) == 256, len(table)
    return table, hashlib.sha256(raw).hexdigest()


def main():
    table, sha = extract(sys.argv[1])
    out = {
        "fonte": "Handy (libretro-handy) lynx/c65c02.h",
        "url": "https://raw.githubusercontent.com/libretro/libretro-handy/master/lynx/c65c02.h",
        "sha256_do_arquivo_lido": sha,
        "licenca_da_fonte": "zlib-style (K. Wilkins); aqui só dados derivados, nenhum código copiado",
        "semantica": "ciclos do datasheet = n + 1; Handy não modela cruzamento de página, desvio tomado nem decimal",
        "opcodes": table,
    }
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "handy_reference.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    ill = sum(1 for v in table.values() if v["op"] == "ILLEGAL")
    print("256 opcodes (%d ilegais) -> %s" % (ill, os.path.normpath(dst)))


if __name__ == "__main__":
    main()
