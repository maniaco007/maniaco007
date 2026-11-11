"""Gera o corpus do teste diferencial (lynx2c -> C -> gcc  vs.  núcleo de referência).

Saídas em <outdir>:
  tests_gen.c   funções C geradas pelo lynx2c + tabela lx_test_fns[]
  vectors.bin   vetores (estado inicial, memória lida, estado/escritas esperados)
  fns.txt       índice -> org, bytes, disassembly (diagnóstico de falhas)

Corpus:
  1. EXAUSTIVO  ADC/SBC/CMP imediato: M(256) x A(256) x C(2) x D(2) = 262144 vetores por opcode
  2. SINGLE     cada um dos 35 opcodes x N codificações de operando (bordas de região/página/ZP)
  3. BLOCOS     sequências aleatórias de 2..8 instruções (exercita vivacidade de flags e soma de ciclos)
Semente fixa => corpus reproduzível.

Formato de vectors.bin (little-endian):
  'LXV1' u32 nvec
  por vetor: u16 fn | u8 a x y s p | u16 next_pc | u16 n_setup {u16 addr,u8 val}*
             | u8 a x y s p | u32 cycles | u16 n_ramw {u16,u8}* | u16 n_iow {u16,u8}*
"""
import os
import random
import struct
import sys

from lynx2c.decode import decode_block
from lynx2c.emit_c import _HEADER, emit_functions
from lynx2c import ABI_VERSION, __version__
from lynx2c.pipeline import analyze
from lynx2c.lift import lift
from lynx2c.opt import flag_liveness
from lynxtrace.core65c02 import RefCpu, RefMem, REF_OPS as _ALL_OPS, FLOW_MNEMONICS, is_bit_branch, ref_table

# corpus de BLOCOS RETOS: só opcodes sequenciais (o fluxo de controle é testado em gen_programs.py)
REF_OPS = {k: v for k, v in _ALL_OPS.items() if v[0] not in FLOW_MNEMONICS}

EDGE = [0x00, 0x01, 0x02, 0x0A, 0x0F, 0x10, 0x7F, 0x80, 0x81, 0x99, 0x9A, 0xFE, 0xFF]


def rv(rng):
    return rng.choice(EDGE) if rng.random() < 0.5 else rng.randrange(256)


def rand_zp(rng):
    return rng.choice([0x00, 0x01, 0xFE, 0xFF, rng.randrange(256), rng.randrange(256)])


def rand_abs(rng, indexed):
    k = rng.randrange(10)
    if indexed and k < 4:
        return rng.choice([0xFBF0, 0xFBFF, 0xFC00 - rng.randrange(1, 0x120), 0x12F0 + rng.randrange(16),
                           0xFCFF - rng.randrange(0x20), 0xFDF0 + rng.randrange(16), 0xFFF0 + rng.randrange(16)])
    if k < 5:
        return rng.randrange(0xFC00)
    if k < 7:
        return rng.randrange(0xFC00, 0xFE00)           # E/S
    if k < 8:
        return rng.randrange(0xFE00, 0x10000)          # ROM/vetores (RAM por baixo)
    return rng.choice([0x0000, 0x00FF, 0x0100, 0x01FF, 0xFBFF, 0xFC00, 0xFCFF, 0xFD00, 0xFDFF, 0xFE00, 0xFFFF])


def encode(opcode, mode, rng):
    if mode in ("nop1", "nop2", "nop3"):               # NOPs indocumentados: operando arbitrário, nunca lido
        n = {"nop1": 0, "nop2": 1, "nop3": 2}[mode]
        return bytes([opcode] + [rng.choice([0x00, 0xFC, 0xFD, 0xFF, rng.randrange(256)]) for _ in range(n)])
    if mode == "imm":
        return bytes([opcode, rv(rng)])
    if mode in ("imp", "acc"):
        return bytes([opcode])
    if mode in ("zp", "zpx", "zpy", "izx", "izy", "izp"):
        return bytes([opcode, rand_zp(rng)])
    a = rand_abs(rng, mode in ("absx", "absy"))
    return bytes([opcode, a & 0xFF, a >> 8])


class Corpus:
    def __init__(self, outdir, seed=0x4C594E58):
        self.out = outdir
        self.rng = random.Random(seed)
        self.fns = []            # (org, code)
        self.vecs = bytearray()
        self.nvec = 0

    def add_fn(self, code, org=0x0200, model="lynx1"):
        self.fns.append((org, bytes(code), model))
        return len(self.fns) - 1

    def add_vec(self, fn, regs=None, p=None, rng=None):
        rng = rng or self.rng
        org, code, model = self.fns[fn]
        mem = RefMem(rng, value_fn=lambda r: rv(r) if r.random() < 0.5 else r.randrange(256))
        cpu = RefCpu(mem, model=model)
        regs = regs or {}
        cpu.a = regs.get("a", rv(rng)); cpu.x = regs.get("x", rv(rng))
        cpu.y = regs.get("y", rv(rng)); cpu.s = regs.get("s", rng.randrange(256))
        if p is None:
            p = (rng.randrange(256) & ~0x10) | 0x20                 # B=0
            if rng.random() < 0.35:
                p |= 0x08
            else:
                p &= ~0x08
        if "c" in regs:
            p = (p & ~1) | regs["c"]
        if "d" in regs:
            p = (p & ~0x08) | (regs["d"] << 3)
        cpu.set_p(p)
        init = (cpu.a, cpu.x, cpu.y, cpu.s, cpu.pack_p())
        cpu.run(code)
        st = cpu.state()
        next_pc = (org + len(code)) & 0xFFFF
        b = self.vecs
        b += struct.pack("<HBBBBBHH", fn, *init, next_pc, len(mem.setup))
        for addr, val in mem.setup:
            b += struct.pack("<HB", addr, val)
        b += struct.pack("<BBBBBI", st["a"], st["x"], st["y"], st["s"], st["p"], st["cycles"])
        b += struct.pack("<H", len(mem.written))
        for addr, val in sorted(mem.written.items()):
            b += struct.pack("<HB", addr, val)
        b += struct.pack("<H", len(mem.io_writes))
        for addr, val in mem.io_writes:
            b += struct.pack("<HB", addr, val)
        self.nvec += 1

    def write(self):
        os.makedirs(self.out, exist_ok=True)
        phase = int(os.environ.get("LX_PHASE", "2"))
        parts, names, lines = [_HEADER % {"ver": __version__, "abi": ABI_VERSION}], [], []
        for i, (org, code, model) in enumerate(self.fns):
            cfg, ops = analyze(code, org, [org], cpu=model)  # código reto: 1 bloco => 1 rotina
            text, where = emit_functions(i, cfg, ops, phase)
            parts.append(text)
            names.append(where[org][0])
            lines.append("%05d $%04X %s %s ; %s" % (i, org, model, code.hex(), " | ".join(x.text() for b in cfg.blocks.values() for x in b.insns)))
        src = "\n".join(parts)
        src += "\nconst LxTestFn lx_test_fns[] = {\n"
        src += "".join("    %s,\n" % n for n in names)
        src += "};\nconst unsigned lx_test_nfns = %d;\n" % len(self.fns)
        src = src.replace('#include "lynx/lx_alu.h"\n', '#include "lynx/lx_alu.h"\ntypedef lx_u32 (*LxTestFn)(LxCpu *cpu, lx_u32 entry);\n', 1)
        with open(os.path.join(self.out, "tests_gen.c"), "w", encoding="utf-8") as f:
            f.write(src)
        with open(os.path.join(self.out, "fns.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        with open(os.path.join(self.out, "vectors.bin"), "wb") as f:
            f.write(b"LXV1" + struct.pack("<I", self.nvec))
            f.write(self.vecs)


def build(outdir, n_variants=10, n_vec=60, n_blocks=200, n_block_vec=60, exhaustive=True):
    c = Corpus(outdir)
    rng = c.rng
    if exhaustive:                                  # 1. exaustivo ADC/SBC imediato
        for opc in (0x69, 0xE9, 0xC9):                # ADC #, SBC #, CMP #
            for m in range(256):
                fn = c.add_fn([opc, m])
                for a in range(256):
                    for cin in (0, 1):
                        for d in (0, 1):
                            c.add_vec(fn, regs={"a": a, "c": cin, "d": d})
    for opc, (mn, mode) in sorted(REF_OPS.items()):  # 2. single
        for _ in range(n_variants):
            fn = c.add_fn(encode(opc, mode, rng), org=rng.randrange(0x10000 - 3))
            for _ in range(n_vec):
                c.add_vec(fn)
    opcs = sorted(REF_OPS)
    for _ in range(n_blocks):                       # 3. blocos
        code = b""
        for _ in range(rng.randrange(2, 9)):
            opc = rng.choice(opcs)
            code += encode(opc, REF_OPS[opc][1], rng)
        fn = c.add_fn(code, org=rng.randrange(0x10000 - len(code)))
        for _ in range(n_block_vec):
            c.add_vec(fn)
    # 4. extensões de modelo (docs/12 §2): NOPs indocumentados (todos os 1/2/3 bytes, inclui $CB/$DB) em Lynx I e II,
    #    RMBn/SMBn em Lynx II; singles + blocos que MISTURAM extensões com instruções normais. BBR/BBS: ver gen_programs.
    for model in ("lynx1", "lynx2"):
        full = ref_table(model)
        ext = sorted(o for o, v in full.items() if o not in _ALL_OPS and not is_bit_branch(v[0]))
        for opc in ext:
            mn, mode = full[opc]
            for _ in range(max(2, n_variants // 3)):
                fn = c.add_fn(encode(opc, mode, rng), org=rng.randrange(0x10000 - 3), model=model)
                for _ in range(max(8, n_vec // 4)):
                    c.add_vec(fn)
        pool = sorted(REF_OPS) + ext * 3                  # extensões com peso maior
        for _ in range(max(40, n_blocks // 3)):
            code = b""
            for _ in range(rng.randrange(2, 9)):
                opc = rng.choice(pool)
                mn, mode = full[opc]
                code += encode(opc, mode, rng)
            fn = c.add_fn(code, org=rng.randrange(0x10000 - len(code)), model=model)
            for _ in range(n_block_vec):
                c.add_vec(fn)
    c.write()
    return c


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "build/test"
    c = build(out, exhaustive=not os.environ.get("LX_LITE"))
    print("funções: %d   vetores: %d   -> %s" % (len(c.fns), c.nvec, out))
