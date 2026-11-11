#!/usr/bin/env python3
"""Confere optable.json (ciclos-base e tamanhos) contra as tabelas do Gearlynx.

Fonte externa (somente leitura, NAO redistribuida aqui): src/m6502_timing.h do
drhelius/Gearlynx (GPLv3). So FATOS (numeros de hardware) sao comparados; nenhum codigo
e copiado. Uso:
    crosscheck_gearlynx.py /caminho/para/Gearlynx/src/m6502_timing.h
Compara TODOS os 256 opcodes de cada modelo (lynx1, lynx2) em ciclos e tamanhos. Codigo de saida 1 se houver
divergencia ou opcode ausente.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lynx2c.optable import Optable  # noqa: E402


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
    tabs = {"lynx1": (_table(src, "k_m6502_opcode_cycles_lynx1"), _table(src, "k_m6502_opcode_sizes_lynx1")),
            "lynx2": (_table(src, "k_m6502_opcode_cycles_lynx2"), _table(src, "k_m6502_opcode_sizes_lynx2"))}
    bad = 0
    for model, (cyc, siz) in tabs.items():
        t = Optable(model=model)
        for op in range(256):
            i = t.get(op)
            if i is None:
                bad += 1
                print("FALTA %s %02X: o Gearlynx executa (c=%d b=%d)" % (model, op, cyc[op], siz[op]))
            elif (i.cycles, i.length) != (cyc[op], siz[op]):
                bad += 1
                print("DIVERGE %s %02X %s: nosso c=%d b=%d / gearlynx c=%d b=%d"
                      % (model, op, i.mnemonic, i.cycles, i.length, cyc[op], siz[op]))
        print("%s: %d opcodes na nossa tabela; comparados com o Gearlynx (ciclos e tamanhos)" % (model, len(t.by_opcode)))
    print("divergencias: %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
