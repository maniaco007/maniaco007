"""Custo ARM por opcode (fase 1): um bloco de UMA instrução por opcode, compilado com clang -> ARM big-endian,
tamanho de cada função lido de `llvm-nm -S`. Mostra o custo FIXO por bloco (prólogo/epílogo/soma de ciclos/teste de
evento) e quais opcodes são caros — roteiro de otimização da fase 2.

Uso: PYTHONPATH=pc-tools/lynx2c python3 pc-tools/lynx2c/tools/opcode_cost.py [-Os] > custo.md
Todos os flags são vivos na saída do bloco (pior caso: sem eliminação entre blocos).
"""
import os
import re
import subprocess
import sys
import tempfile

from lynx2c import ABI_VERSION, __version__, armsize
from lynx2c.emit_c import _HEADER, block_fn_name, emit_block
from lynx2c.optable import Optable
from lynx2c.pipeline import analyze

INC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "runtime", "include")


def operand_bytes(info):
    n = info.length - 1
    if info.mode == "rel":
        return b"\x00"
    return {0: b"", 1: b"\x10", 2: b"\x34\x12"}[n] if info.mode != "imm" else b"\x42"


def main():
    opt = sys.argv[1] if len(sys.argv) > 1 else "-Os"
    if not armsize.available():
        sys.exit("clang/llvm-size ausentes")
    table = Optable()
    parts, names = [_HEADER % {"ver": __version__, "abi": ABI_VERSION}], {}
    for opc, info in sorted(table.by_opcode.items()):
        img = bytes([opc]) + operand_bytes(info)
        cfg, ops = analyze(img, 0x0300, [0x0300])
        nm = "op_%02X" % opc
        parts.append(emit_block(nm, ops[0x0300], 0x0300))
        names[nm] = info
    with tempfile.TemporaryDirectory() as td:
        c, o = os.path.join(td, "c.c"), os.path.join(td, "c.o")
        open(c, "w", encoding="utf-8").write("\n".join(parts))
        r = subprocess.run(["clang"] + armsize.TARGET + [opt, "-ffreestanding", "-std=c89", "-fno-pic", "-w", "-I", INC,
                                                         "-c", c, "-o", o], capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr[:2000])
        nm_out = subprocess.run(["llvm-nm", "-S", "--defined-only", o], capture_output=True, text=True, check=True).stdout
    sizes = {}
    for line in nm_out.splitlines():
        m = re.match(r"[0-9a-f]+ ([0-9a-f]+) [tT] (op_[0-9A-F]{2})$", line)
        if m:
            sizes[m.group(2)] = int(m.group(1), 16) // 4            # instruções ARM
    base = sizes["op_EA"]                                            # NOP = só o custo fixo do bloco
    rows = sorted(((sizes[n], n, i) for n, i in names.items()), reverse=True)
    print("# Custo ARM por opcode — fase 1, clang %s, ARM BE (instruções ARM por bloco de 1 instrução)\n" % opt)
    print("Custo FIXO do bloco (NOP): **%d instruções ARM** (prólogo, soma de ciclos, teste de evento, epílogo).\n" % base)
    print("| Opcode | Instrução | ARM instr. | Líquido (− fixo) |\n|---|---|---:|---:|")
    for s, n, i in rows:
        print("| $%s | %s %s | %d | %d |" % (n[3:], i.mnemonic, i.mode, s, s - base))
    vals = [s - base for s, _, _ in rows]
    print("\nMediana líquida: %d | média líquida: %.1f | máx: %d" % (sorted(vals)[len(vals) // 2], sum(vals) / len(vals), max(vals)))


if __name__ == "__main__":
    main()
