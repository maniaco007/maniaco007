"""Corpus diferencial de PROGRAMAS com fluxo de controle (lynx2c -> C -> lx_run  vs.  referência).

Cada programa é uma imagem de código; o lynx2c gera CFG + overlay; o harness C executa com o
trampolim REAL (lx_run/lx_dispatch/lx_overlay) e para na primeira fronteira de bloco em que
ciclos >= orçamento (YIELD) ou quando o PC não tem código (HALT/unresolved). O núcleo de referência
executa a mesma imagem com a MESMA regra de parada (RefCpu.run_program) e os estados são comparados:
A X Y S P, ciclos, PC de parada, escritas em RAM, escritas em E/S (ordem), PC/razão de parada.

Programas:
  1. ALEATÓRIOS  8..48 instruções: sequenciais + Bcc/BRA/JMP/JSR/RTS/JMP(ind)/JMP(abs,X), alvos em
     fronteiras de instrução (e alguns externos), org perto de limites de página
  2. DIRIGIDOS   laço com contador, sub-rotinas aninhadas, RTS trick, JMP ($xxFF), desvios em limite de página
Formato de programs.bin (little-endian):
  'LXV2' u32 nvec
  por vetor: u16 prog | u8 a x y s p | u16 entry | u32 budget | u16 n_setup {u16 addr,u8 val}*
             | u8 reason(0 yield,1 unresolved) | u16 stop_pc | u8 a x y s p pmask | u32 cycles
             | u16 n_ramw {u16,u8}* | u16 n_iow {u16,u8}*
"""
import os
import random
import struct
import sys

from lynx2c.emit_c import _HEADER, emit_overlay
from lynx2c.pipeline import analyze
from lynx2c import ABI_VERSION, __version__
from independent import independent_leaders
from lynxtrace.core65c02 import RefCpu, RefMem, REF_OPS, FLOW_MNEMONICS, BR_COND, _LEN

OPC = {v: k for k, v in REF_OPS.items()}                      # (mn, mode) -> opcode
SEQ = sorted(v for v in REF_OPS.values() if v[0] not in FLOW_MNEMONICS)
X_WRITERS = {"LDX", "TAX", "TSX", "INX", "DEX", "PLX"}        # mudam X: incompatíveis com JMP (abs,X) de tabela fixa
BRANCHES = sorted(BR_COND)
EDGE = [0x00, 0x01, 0x0A, 0x0F, 0x10, 0x7F, 0x80, 0x99, 0xFE, 0xFF]


def rv(rng):
    return rng.choice(EDGE) if rng.random() < 0.5 else rng.randrange(256)


# ---------------------------------------------------------------- montador mínimo (programas dirigidos)
def assemble(org, items):
    """items: ('L', nome) | (mn, mode, operando) ; operando pode ser int ou nome de rótulo.
    Retorna (bytes, {rótulo: endereço})."""
    labels, addr = {}, org
    for it in items:                                           # passo 1: endereços
        if it[0] == "L":
            labels[it[1]] = addr
        else:
            addr += _LEN[it[1]]
    out, addr = bytearray(), org
    for it in items:                                           # passo 2: bytes
        if it[0] == "L":
            continue
        mn, mode, op = it if len(it) == 3 else (it[0], it[1], None)
        if isinstance(op, str):
            op = labels[op]
        n = _LEN[mode]
        addr_next = addr + n
        if mode == "rel":
            off = op - addr_next
            assert -128 <= off <= 127, (mn, hex(addr), off)
            op = off & 0xFF
        out.append(OPC[(mn, mode)])
        if n == 2:
            out.append(op & 0xFF)
        elif n == 3:
            out += bytes([op & 0xFF, (op >> 8) & 0xFF])
        addr = addr_next
    return bytes(out), labels


# ---------------------------------------------------------------- programas aleatórios
def random_program(rng):
    org = rng.choice([rng.randrange(0x0200, 0xE000), 0x12E0 + rng.randrange(0x20), 0x00F0 + rng.randrange(0x10),
                      0xFBF0 + rng.randrange(8)])
    n = rng.randrange(8, 48)
    iax_prog = rng.random() < 0.10                 # só estes usam JMP (abs,X) e, então, não podem alterar X
    seq_pool = [v for v in SEQ if v[0] not in X_WRITERS] if iax_prog else SEQ
    kinds = []
    for _ in range(n):
        r = rng.random()
        if r < 0.52:
            kinds.append(("seq", rng.choice(seq_pool)))
        elif r < 0.72:
            kinds.append(("br", rng.choice(BRANCHES)))
        elif r < 0.76:
            kinds.append(("bra", None))
        elif r < 0.81:
            kinds.append(("jmp", None))
        elif r < 0.87:
            kinds.append(("jsr", None))
        elif r < 0.91:
            kinds.append(("rts", None))
        elif r < 0.93:
            kinds.append(("rti", None))
        elif r < 0.95:
            kinds.append(("brk", None))
        elif r < 0.97:
            kinds.append(("jind", None))
        else:
            kinds.append(("jiax" if iax_prog else "jind", None))
    if iax_prog and not any(k == "jiax" for k, _ in kinds):
        kinds[rng.randrange(len(kinds))] = ("jiax", None)
    lens = [_LEN[v[1]] if k == "seq" else {"br": 2, "bra": 2, "jmp": 3, "jsr": 3, "rts": 1, "rti": 1, "brk": 2, "jind": 3, "jiax": 3}[k]
            for k, v in kinds]
    starts, a = [], org
    for L in lens:
        starts.append(a)
        a += L
    end = a
    if end > 0x10000:
        return None
    seeds, preset, has_iax = set(), {}, False
    code = bytearray()
    # param_operand: ~35% dos programas marcam operandos imediatos como modificáveis e algumas escritas
    # absolutas passam a mirá-los (o operando é então lido da RAM a cada execução)
    smc_addrs = []
    if rng.random() < 0.35:
        smc_addrs = [starts[i] + 1 for i, (k, v) in enumerate(kinds) if k == "seq" and v[1] == "imm" and rng.random() < 0.6]
    WRITERS = {"STA", "STX", "STY", "STZ", "INC", "DEC", "ASL", "LSR", "ROL", "ROR", "TSB", "TRB"}

    def external():
        while True:
            t = rng.randrange(0x10000)
            if not (org <= t < end):
                return t

    for i, (k, v) in enumerate(kinds):
        a = starts[i]
        if k == "seq":
            mn, mode = v
            if mode == "imm":
                code += bytes([OPC[v], rv(rng)])
            elif _LEN[mode] == 1:
                code.append(OPC[v])
            elif _LEN[mode] == 2:
                code += bytes([OPC[v], rng.choice([0x00, 0x01, 0xFE, 0xFF, rng.randrange(256)])])
            else:
                x = rng.choice([rng.randrange(0xFC00), rng.randrange(0xFC00, 0x10000), 0xFBFF, 0xFC00, 0xFE00])
                if smc_addrs and mode == "abs" and mn in WRITERS and rng.random() < 0.6:
                    x = rng.choice(smc_addrs)                 # esta escrita modifica um operando imediato
                code += bytes([OPC[v], x & 0xFF, x >> 8])
        elif k in ("br", "bra"):
            nxt = a + 2
            cands = [s for s in starts if -128 <= s - nxt <= 127]
            tgt = rng.choice(cands) if cands else nxt
            mn = "BRA" if k == "bra" else v
            code += bytes([OPC[(mn, "rel")], (tgt - nxt) & 0xFF])
        elif k in ("jmp", "jsr"):
            r = rng.random()
            tgt = rng.choice(starts) if r < 0.85 else (external() if r < 0.95 else org)
            code += bytes([OPC[("JMP" if k == "jmp" else "JSR", "abs")], tgt & 0xFF, tgt >> 8])
        elif k == "rts":
            code.append(OPC[("RTS", "imp")])
        elif k == "rti":
            code.append(OPC[("RTI", "imp")])
        elif k == "brk":
            h = rng.choice(starts)                          # handler no vetor IRQ/BRK ($FFFE)
            seeds.add(h)
            preset[0xFFFE], preset[0xFFFF] = h & 0xFF, h >> 8
            code += bytes([OPC[("BRK", "brk")], rng.randrange(256)])
        elif k == "jind":
            cell = rng.randrange(0x0200, 0xEFF0)
            if org <= cell < end or org <= cell + 1 < end:
                cell = 0x0300 if not (org <= 0x0300 < end) else 0xA000
            tgt = rng.choice(starts)
            seeds.add(tgt)
            preset[cell], preset[cell + 1] = tgt & 0xFF, tgt >> 8
            code += bytes([OPC[("JMP", "ind")], cell & 0xFF, cell >> 8])
        else:  # jiax
            has_iax = True
            base = rng.randrange(0x0200, 0xEFF0)
            if any(org <= base + d < end for d in range(8)):
                base = 0xA000 if not (org <= 0xA000 < end) else 0x0300
            for j in range(4):
                tgt = rng.choice(starts)
                seeds.add(tgt)
                preset[base + 2 * j], preset[base + 2 * j + 1] = tgt & 0xFF, tgt >> 8
            code += bytes([OPC[("JMP", "iax")], base & 0xFF, base >> 8])
    for a in smc_addrs:                                   # valor inicial do operando = byte da imagem
        preset[a] = code[a - org]
    return dict(org=org, code=bytes(code), seeds=seeds, preset=preset, x_choices=[0, 2, 4, 6] if has_iax else None,
                s_choices=None, smc=set(smc_addrs))


# ---------------------------------------------------------------- programas dirigidos
def directed_programs():
    P = []
    # 1. laço com contador (SBC sem SEC: depende do C inicial; o orçamento limita)
    code, L = assemble(0x0300, [("LDA", "imm", 5), ("STA", "zp", 0x10),
                                ("L", "loop"), ("LDA", "zp", 0x10), ("SBC", "imm", 1), ("STA", "zp", 0x10),
                                ("BNE", "rel", "loop"),
                                ("LDA", "imm", 0xAA), ("STA", "abs", 0xFC91), ("RTS", "imp")])
    P.append(dict(name="laco_contador", org=0x0300, code=code, seeds=set(), preset={}, x_choices=None, s_choices=None,
                  budget=[40, 200, 1500], carry_set=True))
    # 2. sub-rotinas aninhadas
    code, L = assemble(0x0400, [("JSR", "abs", "f"), ("JSR", "abs", "g"), ("STA", "zp", 0x20), ("RTS", "imp"),
                                ("L", "f"), ("ADC", "imm", 1), ("JSR", "abs", "h"), ("RTS", "imp"),
                                ("L", "g"), ("SBC", "imm", 2), ("RTS", "imp"),
                                ("L", "h"), ("LDA", "izy", 0x30), ("RTS", "imp")])
    P.append(dict(name="subrotinas", org=0x0400, code=code, seeds=set(), preset={}, x_choices=None, s_choices=None,
                  budget=[30, 100, 800]))
    P.append(dict(P[-1], name="subrotinas_precise", precise=True))
    P.append(dict(P[0], name="laco_contador_precise", precise=True))
    # 3. RTS trick: empilha (alvo-1) e executa RTS (S fixo = $FD)
    tgt_lbl = "alvo"
    tmp, L0 = assemble(0x0500, [("LDA", "imm", 0), ("STA", "abs", 0x01FF), ("LDA", "imm", 0), ("STA", "abs", 0x01FE),
                                ("RTS", "imp"), ("L", tgt_lbl), ("ADC", "imm", 7), ("STA", "zp", 0x40),
                                ("BRA", "rel", tgt_lbl)])   # 1ª passada só para descobrir o endereço do alvo
    t = L0[tgt_lbl] - 1
    code, L = assemble(0x0500, [("LDA", "imm", t >> 8), ("STA", "abs", 0x01FF), ("LDA", "imm", t & 0xFF),
                                ("STA", "abs", 0x01FE), ("RTS", "imp"), ("L", tgt_lbl), ("ADC", "imm", 7),
                                ("STA", "zp", 0x40), ("BRA", "rel", tgt_lbl)])
    P.append(dict(name="rts_trick", org=0x0500, code=code, seeds={L[tgt_lbl]}, preset={}, x_choices=None,
                  s_choices=[0xFD], budget=[60, 300]))
    # 4. JMP ($10FF): ponteiro cruzando página (65C02 lê o byte alto de $1100)
    code, L = assemble(0x0600, [("JMP", "ind", 0x10FF), ("L", "dest"), ("LDA", "imm", 0x42), ("STA", "zp", 0x50),
                                ("BRA", "rel", "dest")])
    P.append(dict(name="jmp_ind_pagina", org=0x0600, code=code, seeds={L["dest"]},
                  preset={0x10FF: L["dest"] & 0xFF, 0x1100: L["dest"] >> 8, 0x1000: 0xEE},
                  x_choices=None, s_choices=None, budget=[30, 120]))
    # 5. desvios em limite de página (alvo e instrução seguinte em páginas diferentes)
    code, L = assemble(0x12F4, [("L", "a"), ("LDA", "izp", 0x20), ("BNE", "rel", "b"), ("ADC", "imm", 1),
                                ("BCC", "rel", "a"), ("L", "b"), ("SBC", "imm", 1), ("BMI", "rel", "a"),
                                ("BRA", "rel", "c"), ("ADC", "imm", 0),
                                ("L", "c"), ("BVS", "rel", "a"), ("BRA", "rel", "a")])
    P.append(dict(name="desvios_pagina", org=0x12F4, code=code, seeds=set(), preset={}, x_choices=None,
                  s_choices=None, budget=[40, 150, 700]))
    # 6. JMP (abs,X)
    code, L = assemble(0x0700, [("JMP", "iax", 0x2000), ("L", "d0"), ("ADC", "imm", 1), ("BRA", "rel", "d0"),
                                ("L", "d1"), ("SBC", "imm", 1), ("BRA", "rel", "d1"),
                                ("L", "d2"), ("LDA", "imm", 9), ("BRA", "rel", "d2"),
                                ("L", "d3"), ("STA", "abs", 0xFD10), ("BRA", "rel", "d3")])
    pre = {}
    for j, nm in enumerate(["d0", "d1", "d2", "d3"]):
        pre[0x2000 + 2 * j], pre[0x2001 + 2 * j] = L[nm] & 0xFF, L[nm] >> 8
    P.append(dict(name="jmp_iax", org=0x0700, code=code, seeds={L[n] for n in ("d0", "d1", "d2", "d3")},
                  preset=pre, x_choices=[0, 2, 4, 6], s_choices=None, budget=[30, 200]))
    # 7. BRK -> handler -> RTI (volta em addr+2) com P empilhado com B=1
    code, L = assemble(0x0800, [("SEC", "imp"), ("LDA", "imm", 1), ("BRK", "brk", 0xAB), ("ADC", "imm", 1),
                                ("STA", "zp", 0x10), ("BRA", "rel", "fim"), ("L", "h"), ("INC", "zp", 0x20),
                                ("PHP", "imp"), ("PLA", "imp"), ("STA", "zp", 0x21), ("RTI", "imp"),
                                ("L", "fim"), ("BRA", "rel", "fim")])
    P.append(dict(name="brk_rti", org=0x0800, code=code, seeds={L["h"]},
                  preset={0xFFFE: L["h"] & 0xFF, 0xFFFF: L["h"] >> 8}, x_choices=None, s_choices=None,
                  budget=[20, 60, 400]))
    # 8. laço com X e pilha (PHA/PLA/PHP/PLP/TXS/TSX)
    code, L = assemble(0x0900, [("LDX", "imm", 5), ("L", "a"), ("TXA", "imp"), ("PHA", "imp"), ("DEX", "imp"),
                                ("BNE", "rel", "a"), ("LDX", "imm", 5), ("L", "b"), ("PLA", "imp"), ("ADC", "imm", 3),
                                ("DEX", "imp"), ("BNE", "rel", "b"), ("TSX", "imp"), ("STX", "zp", 0x30),
                                ("PHP", "imp"), ("PLP", "imp"), ("RTS", "imp")])
    P.append(dict(name="pilha_laco_x", org=0x0900, code=code, seeds=set(), preset={}, x_choices=None,
                  s_choices=[0xFF, 0x08, 0x02], budget=[30, 120, 700]))
    # 9. deslocamentos e BIT/TSB/TRB sobre memória e acumulador
    code, L = assemble(0x0A00, [("LDA", "zp", 0x40), ("ASL", "acc"), ("ROL", "zp", 0x41), ("LSR", "abs", 0x2000),
                                ("ROR", "zpx", 0x42), ("INC", "absx", 0x20FF), ("DEC", "acc"), ("BIT", "zp", 0x43),
                                ("TSB", "zp", 0x44), ("TRB", "abs", 0x2001), ("CMP", "izy", 0x50),
                                ("BCS", "rel", "e"), ("ORA", "imm", 0x80), ("EOR", "izx", 0x52), ("L", "e"),
                                ("STZ", "absx", 0x2100), ("BRA", "rel", "e")])
    P.append(dict(name="shifts_bit_rmw", org=0x0A00, code=code, seeds=set(), preset={}, x_choices=None,
                  s_choices=None, budget=[40, 200]))
    # 10. SMC de operando imediato: STA/INC sobre o operando do ADC # e do SBC # (param_operand)
    items = lambda ao, so: [("LDA", "imm", 0x07), ("STA", "abs", ao), ("L", "adc"), ("ADC", "imm", 0x00),
                            ("STA", "zp", 0x10), ("INC", "abs", ao), ("L", "sbc"), ("SBC", "imm", 0x00),
                            ("STA", "abs", so), ("DEC", "abs", ao), ("STA", "zp", 0x11), ("BRA", "rel", "adc")]
    _, L0 = assemble(0x0B00, items(0, 0))
    ao, so = L0["adc"] + 1, L0["sbc"] + 1
    code, L = assemble(0x0B00, items(ao, so))
    P.append(dict(name="smc_imediato", org=0x0B00, code=code, seeds=set(), preset={ao: code[ao - 0x0B00], so: code[so - 0x0B00]},
                  x_choices=None, s_choices=None, budget=[30, 120, 600], smc={ao, so}))
    return P


# ---------------------------------------------------------------- corpus
class Corpus:
    def __init__(self, outdir, seed=0x464C4F57):
        self.out, self.rng = outdir, random.Random(seed)
        self.progs, self.vecs, self.nvec = [], bytearray(), 0

    def add_program(self, prog, nvec):
        entries = [prog["org"]] + sorted(prog["seeds"])
        cfg, ops = analyze(prog["code"], prog["org"], entries, prog.get("precise", False), prog.get("smc", ()))
        # a referência para onde o TRADUTOR para: garantir que os líderes dele são os corretos
        want = independent_leaders(prog["code"], prog["org"], entries)
        assert set(cfg.blocks) == want, "líderes do CFG divergem do algoritmo independente: %s" % sorted(
            set(cfg.blocks) ^ want)
        pid = len(self.progs)
        self.progs.append((prog, cfg, ops))
        rng = self.rng
        for _ in range(nvec):
            entry = prog["org"]
            budget = rng.choice(prog.get("budget") or [8, 30, 100, 250, 600])
            self.add_vec(pid, entry, budget, prog, cfg)
        return pid

    def add_vec(self, pid, entry, budget, prog, cfg):
        rng = self.rng
        mem = RefMem(rng, value_fn=lambda r: rv(r) if r.random() < 0.5 else r.randrange(256), preset=prog["preset"])
        mem.setup = sorted(prog["preset"].items())
        cpu = RefCpu(mem)
        cpu.a, cpu.y = rv(rng), rv(rng)
        cpu.x = rng.choice(prog["x_choices"]) if prog["x_choices"] else rv(rng)
        cpu.s = rng.choice(prog["s_choices"]) if prog["s_choices"] else rng.randrange(256)
        p = (rng.randrange(256) & ~0x10) | 0x20
        p = (p | 0x08) if rng.random() < 0.3 else (p & ~0x08)
        if prog.get("carry_set") and rng.random() < 0.7:
            p |= 1
        cpu.set_p(p)
        init = (cpu.a, cpu.x, cpu.y, cpu.s, cpu.pack_p())
        reason, stop_pc = cpu.run_program(prog["code"], prog["org"], set(cfg.blocks), entry, budget, prog.get("smc", ()))
        st = cpu.state()
        # P comparável: no YIELD em bloco conhecido, flags N V Z C MORTOS ali podem estar desatualizados
        # (garantia do tradutor; ver opt.cfg_liveness). Em PC não resolvido: tudo vivo => P exato.
        pmask = 0xFF
        # modo precise: P exato SEMPRE (máscara 0xFF independente do tradutor)
        if reason == "yield" and not prog.get("precise") and stop_pc in cfg.live_in:
            live = cfg.live_in[stop_pc]
            for f, bit in (("N", 0x80), ("V", 0x40), ("Z", 0x02), ("C", 0x01)):
                if f not in live:
                    pmask &= ~bit
        b = self.vecs
        b += struct.pack("<HBBBBBHIH", pid, *init, entry, budget, len(mem.setup))
        for addr, val in mem.setup:
            b += struct.pack("<HB", addr, val)
        b += struct.pack("<BHBBBBBBI", 0 if reason == "yield" else 1, stop_pc,
                         st["a"], st["x"], st["y"], st["s"], st["p"], pmask, st["cycles"])
        b += struct.pack("<H", len(mem.written))
        for addr, val in sorted(mem.written.items()):
            b += struct.pack("<HB", addr, val)
        b += struct.pack("<H", len(mem.io_writes))
        for addr, val in mem.io_writes:
            b += struct.pack("<HB", addr, val)
        self.nvec += 1

    def write(self):
        os.makedirs(self.out, exist_ok=True)
        parts = [_HEADER % {"ver": __version__, "abi": ABI_VERSION}]
        lines = []
        for pid, (prog, cfg, ops) in enumerate(self.progs):
            parts.append(emit_overlay(pid, cfg, ops))
            lines.append("prog %04d org=$%04X blocos=%d %s%s :: %s" % (
                pid, prog["org"], len(cfg.blocks), prog.get("name", "aleatorio"),
                " [precise]" if prog.get("precise") else "", prog["code"].hex()))
        parts.append("const LxOverlay *const lx_test_ovs[] = {\n%s\n};\nconst unsigned lx_test_novs = %d;\n" % (
            ",\n".join("    &lx_ov%d" % i for i in range(len(self.progs))), len(self.progs)))
        with open(os.path.join(self.out, "progs_gen.c"), "w", encoding="utf-8") as f:
            f.write("\n".join(parts))
        with open(os.path.join(self.out, "progs.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        with open(os.path.join(self.out, "programs.bin"), "wb") as f:
            f.write(b"LXV2" + struct.pack("<I", self.nvec))
            f.write(self.vecs)


def build(outdir, n_random=220, nvec_random=40, nvec_directed=120):
    c = Corpus(outdir)
    for prog in directed_programs():
        c.add_program(prog, nvec_directed)
    made = 0
    while made < n_random:
        prog = random_program(c.rng)
        if prog is None:
            continue
        prog["precise"] = (made % 3 == 0)      # 1/3 dos programas no modo P exato
        c.add_program(prog, nvec_random)
        made += 1
    c.write()
    return c


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "build/test"
    c = build(out)
    print("programas: %d   vetores: %d   -> %s" % (len(c.progs), c.nvec, out))
