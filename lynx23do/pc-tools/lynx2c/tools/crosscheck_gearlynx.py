#!/usr/bin/env python3
"""Confere optable.json (ciclos-base e tamanhos) contra as tabelas do Gearlynx.

Fonte externa (somente leitura, NAO redistribuida aqui): src/m6502_timing.h do
drhelius/Gearlynx (GPLv3). So FATOS (numeros de hardware) sao comparados; nenhum codigo
e copiado. Uso:
    crosscheck_gearlynx.py /caminho/para/Gearlynx/src/m6502_timing.h
Saida: divergencias de ciclo/tamanho e os opcodes que o Lynx executa e nos nao decodificamos
(NOPs multi-byte do Lynx I; RMB/SMB/BBR/BBS do Lynx II). Codigo de saida 1 se houver divergencia.
"""
import json
import re
import sys
from pathlib import Path

OPTABLE = Path(__file__).resolve().parent.parent / "lynx2c" / "optable.json"


def _table(src, name):
    m = re.search(name + r"\[256\]\s*=\s*\{(.*?)\};", src, re.S)
    if not m:
        raise SystemExit("tabela %s nao encontrada" % name)
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)
    vals = [int(x) for x in re.findall(r"\d+", body)]
    if len(vals) != 256:
        raise SystemExit("tabela %s com %d entradas" % (name, len(vals)))
    return vals


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    src = Path(argv[1]).read_text()
    c1 = _table(src, "k_m6502_opcode_cycles_lynx1")
    c2 = _table(src, "k_m6502_opcode_cycles_lynx2")
    s1 = _table(src, "k_m6502_opcode_sizes_lynx1")
    s2 = _table(src, "k_m6502_opcode_sizes_lynx2")
    d = json.loads(OPTABLE.read_text())
    mine = {int(o["opcode"], 16): o for o in d["ops"]}
    bad = 0
    for op, o in sorted(mine.items()):
        size = d["modes"][o["mode"]]["bytes"]
        for tag, cyc, siz in (("lynx1", c1, s1), ("lynx2", c2, s2)):
            if o["cycles"] != cyc[op] or size != siz[op]:
                bad += 1
                print("DIVERGE %s %02X %s: nosso c=%d b=%d / gearlynx c=%d b=%d"
                      % (tag, op, o["mnemonic"], o["cycles"], size, cyc[op], siz[op]))
    print("opcodes comparados: %d (Lynx I e II), divergencias: %d" % (len(mine), bad))
    for tag, cyc, siz in (("Lynx I", c1, s1), ("Lynx II", c2, s2)):
        miss = [(i, cyc[i], siz[i]) for i in range(256) if i not in mine and cyc[i] != 1]
        print("%s: executa e nao decodificamos (op, ciclos, bytes): %s"
              % (tag, ", ".join("%02X/%d/%d" % t for t in miss)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
