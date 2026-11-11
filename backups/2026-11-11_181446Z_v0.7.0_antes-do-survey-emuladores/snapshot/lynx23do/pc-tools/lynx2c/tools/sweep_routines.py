"""Varre o limite de blocos por rotina (fase 2) e mede o código ARM REAL (clang -> ARM big-endian) e o maior quadro de pilha.

Uso (PYTHONPATH=pc-tools/lynx2c):
  python3 pc-tools/lynx2c/tools/sweep_routines.py IMAGEM.bin --org 0 --entry 0x400 [--entry A]... \
         [--smc-operand A]... [--hook A]... [--limits 0,64,32,16,8,4,2]

Mostra, para a fase 1 e para a fase 2 com cada limite: nº de rotinas, bytes ARM, expansão (bytes ARM / byte de 65C02),
instruções ARM por instrução 65C02 e o MAIOR QUADRO DE PILHA (um quadro grande estoura a pilha de uma tarefa do 3DO).
Referência medida (Dormann 6502, docs/04 §3.4): sem limite 25,4x e quadro de 15 360 B; 32 blocos 17,7x e 44 B.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

from lynx2c import ABI_VERSION, __version__, armsize
from lynx2c.emit_c import _HEADER, emit_overlay
from lynx2c.pipeline import analyze
from lynx2c.routines import partition

INC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "runtime", "include")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--org", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--entry", type=lambda s: int(s, 0), action="append", default=None)
    ap.add_argument("--smc-operand", type=lambda s: int(s, 0), action="append", default=[])
    ap.add_argument("--hook", type=lambda s: int(s, 0), action="append", default=[])
    ap.add_argument("--limits", default="0,64,32,16,8,4,2")
    ap.add_argument("--opt", default="-Os")
    a = ap.parse_args()
    if not armsize.available():
        sys.exit("clang/llvm-size ausentes")
    img = open(a.image, "rb").read()
    cfg, ops = analyze(img, a.org, a.entry or [a.org], False, a.smc_operand, a.hook)
    nb = len(cfg.blocks)
    ni = sum(len(b.insns) for b in cfg.blocks.values())
    by = sum(i.length for b in cfg.blocks.values() for i in b.insns)
    print("blocos %d, instruções %d, bytes de 65C02 %d\n" % (nb, ni, by))
    print("%-9s %8s %11s %9s %7s %13s" % ("limite", "rotinas", "ARM total", "expansão", "ARM/i", "maior quadro"))
    for phase, mb in [(1, 0)] + [(2, int(x)) for x in a.limits.split(",")]:
        with tempfile.TemporaryDirectory() as td:
            c, s = os.path.join(td, "g.c"), os.path.join(td, "g.s")
            open(c, "w", encoding="utf-8").write(_HEADER % {"ver": __version__, "abi": ABI_VERSION} + "\n" +
                                                 emit_overlay(0, cfg, ops, phase=phase, max_blocks=mb))
            m = armsize.measure_c(c, INC, a.opt)
            subprocess.run(["clang"] + armsize.TARGET + [a.opt, "-ffreestanding", "-std=c89", "-fno-pic", "-w", "-I", INC,
                                                         "-S", c, "-o", s], check=True)
            frames = [int(x) for x in re.findall(r"sub\s+sp, sp, #(\d+)", open(s).read())]
        tot = m["text"] + m["rodata"]
        nr = nb if phase == 1 else len(partition(cfg, mb))
        label = "fase 1" if phase == 1 else ("∞" if mb == 0 else str(mb))
        print("%-9s %8d %11d %8.1fx %7.1f %11d B" % (label, nr, tot, tot / by, m["text"] / 4 / ni, max(frames) if frames else 0))


if __name__ == "__main__":
    main()
