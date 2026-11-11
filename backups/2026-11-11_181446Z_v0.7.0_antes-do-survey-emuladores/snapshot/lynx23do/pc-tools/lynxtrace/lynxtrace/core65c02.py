"""Núcleo de referência 65C02 — escrito de forma INDEPENDENTE do tradutor.

Independência deliberada (para o teste diferencial ter valor):
  - opcodes DERIVADOS do padrão de bits 'aaabbbcc' do 6502 nos grupos regulares (não copiados do
    optable.json do lynx2c); só os opcodes irregulares (implícitos, STZ abs, BRK/RTI, JMP/JSR…) são listados;
  - modos de endereçamento e ciclos calculados por REGRAS (base_cycles / page_cross_applies), não por tabela;
  - ADC/SBC decimais em Python com inteiros, a partir da descrição de Bruce Clark (mesma FONTE de semântica
    que o C, código distinto); cobertura extra por PROPRIEDADE (test_reference_core.py).

Modelo de memória (espelha o harness C):
  - RAM: dict esparso; 1ª leitura de endereço nunca escrito sorteia um valor e o REGISTRA em 'setup';
  - $FC00-$FDFF: E/S — leitura devolve io_value(addr) (por chip); escritas vão para 'io_writes' (ordem);
    $FE00-$FFFF: RAM por baixo (igual a lx_mem.c).
Flag B: só existe no P EMPILHADO (PHP/BRK empilham B=1); PLP/RTI o ignoram; internamente fica 0.
"""

IO_LO, IO_HI = 0xFC00, 0xFDFF


def io_value(addr):
    """Valor lido de E/S (igual aos stubs do harness C). DIFERE por região (Suzy x Mikey),
    para que um acesso roteado ao chip errado seja detectado pelo teste diferencial."""
    if addr <= 0xFCFF:
        return (addr * 7 + 13) & 0xFF      # Suzy  $FC00-$FCFF
    return (addr * 11 + 5) & 0xFF          # Mikey $FD00-$FDFF


# ---- tabela de opcodes derivada do padrão aaabbbcc -----------------------------------------------
def _pat(aaa, bbb, cc):
    return (aaa << 5) | (bbb << 2) | cc


_G1 = {"ORA": 0b000, "AND": 0b001, "EOR": 0b010, "ADC": 0b011, "STA": 0b100, "LDA": 0b101, "CMP": 0b110, "SBC": 0b111}
_G1_MODE = {0b000: "izx", 0b001: "zp", 0b010: "imm", 0b011: "abs",
            0b100: "izy", 0b101: "zpx", 0b110: "absy", 0b111: "absx"}


def build_ref_table():
    t = {}
    # cc=01: grupo 1; (zp) = aaa 100 10 ($x2); $89 (aaa=100,bbb=010) é BIT #, não STA #
    for mn, aaa in _G1.items():
        for bbb, mode in _G1_MODE.items():
            if mn == "STA" and mode == "imm":
                t[_pat(aaa, bbb, 1)] = ("BIT", "imm")
            else:
                t[_pat(aaa, bbb, 1)] = (mn, mode)
        t[(aaa << 5) | 0x12] = (mn, "izp")
    # cc=10: deslocamentos (aaa 000..011), DEC/INC (110/111), STX/LDX (100/101)
    for mn, aaa in (("ASL", 0), ("ROL", 1), ("LSR", 2), ("ROR", 3)):
        for bbb, mode in ((1, "zp"), (2, "acc"), (3, "abs"), (5, "zpx"), (7, "absx")):
            t[_pat(aaa, bbb, 2)] = (mn, mode)
    for mn, aaa in (("DEC", 6), ("INC", 7)):
        for bbb, mode in ((1, "zp"), (3, "abs"), (5, "zpx"), (7, "absx")):
            t[_pat(aaa, bbb, 2)] = (mn, mode)
    for bbb, mode in ((1, "zp"), (3, "abs"), (5, "zpy")):
        t[_pat(4, bbb, 2)] = ("STX", mode)
    for bbb, mode in ((0, "imm"), (1, "zp"), (3, "abs"), (5, "zpy"), (7, "absy")):
        t[_pat(5, bbb, 2)] = ("LDX", mode)
    t[0x1A] = ("INC", "acc")                   # 65C02 (aaa=000 bbb=110 cc=10)
    t[0x3A] = ("DEC", "acc")                   # 65C02 (aaa=001 bbb=110 cc=10)
    t[0x9E] = ("STZ", "absx")                  # 65C02
    # cc=00: BIT, STY/LDY, CPY/CPX, TSB/TRB, STZ
    for bbb, mode in ((1, "zp"), (3, "abs"), (5, "zpx"), (7, "absx")):
        t[_pat(1, bbb, 0)] = ("BIT", mode)
    for bbb, mode in ((1, "zp"), (3, "abs"), (5, "zpx")):
        t[_pat(4, bbb, 0)] = ("STY", mode)
    for bbb, mode in ((0, "imm"), (1, "zp"), (3, "abs"), (5, "zpx"), (7, "absx")):
        t[_pat(5, bbb, 0)] = ("LDY", mode)
    for mn, aaa in (("CPY", 6), ("CPX", 7)):
        for bbb, mode in ((0, "imm"), (1, "zp"), (3, "abs")):
            t[_pat(aaa, bbb, 0)] = (mn, mode)
    for bbb, mode in ((1, "zp"), (3, "abs")):
        t[_pat(0, bbb, 0)] = ("TSB", mode)
    for bbb, mode in ((5, "zp"), (7, "abs")):
        t[_pat(0, bbb, 0)] = ("TRB", mode)
    t[0x64] = ("STZ", "zp")
    t[0x74] = ("STZ", "zpx")
    t[0x9C] = ("STZ", "abs")
    # implícitos (irregulares): lista explícita
    for opc, mn in {0xE8: "INX", 0xC8: "INY", 0xCA: "DEX", 0x88: "DEY", 0xAA: "TAX", 0x8A: "TXA", 0xA8: "TAY",
                    0x98: "TYA", 0xBA: "TSX", 0x9A: "TXS", 0x18: "CLC", 0x38: "SEC", 0x58: "CLI", 0x78: "SEI",
                    0xB8: "CLV", 0xD8: "CLD", 0xF8: "SED", 0xEA: "NOP", 0x48: "PHA", 0x68: "PLA", 0xDA: "PHX",
                    0xFA: "PLX", 0x5A: "PHY", 0x7A: "PLY", 0x08: "PHP", 0x28: "PLP"}.items():
        t[opc] = (mn, "imp")
    return t


# ---- fluxo de controle ------------------------------------------------------------------
# Desvios condicionais: padrão xxy10000 — xx escolhe o flag (00 N, 01 V, 10 C, 11 Z) e y = valor
# do flag que FAZ o desvio. BPL=$10 BMI=$30 BVC=$50 BVS=$70 BCC=$90 BCS=$B0 BNE=$D0 BEQ=$F0.
_BR_NAMES = {("N", 0): "BPL", ("N", 1): "BMI", ("V", 0): "BVC", ("V", 1): "BVS",
             ("C", 0): "BCC", ("C", 1): "BCS", ("Z", 0): "BNE", ("Z", 1): "BEQ"}
BR_COND = {}                                   # mnemônico -> (flag, valor)


def _build_flow():
    t = {}
    for xx, f in enumerate("NVCZ"):
        for y in (0, 1):
            t[(xx << 6) | (y << 5) | 0x10] = (_BR_NAMES[(f, y)], "rel")
            BR_COND[_BR_NAMES[(f, y)]] = (f, y)
    t[0x80] = ("BRA", "rel")                   # 65C02
    t[0x4C] = ("JMP", "abs")
    t[0x6C] = ("JMP", "ind")
    t[0x7C] = ("JMP", "iax")                   # 65C02
    t[0x20] = ("JSR", "abs")
    t[0x60] = ("RTS", "imp")
    t[0x00] = ("BRK", "brk")                   # 2 bytes: o segundo é a "assinatura"
    t[0x40] = ("RTI", "imp")
    return t


FLOW_OPS = _build_flow()
FLOW_MNEMONICS = {"BRA", "JMP", "JSR", "RTS", "BRK", "RTI"} | set(BR_COND)
REF_OPS = build_ref_table()
REF_OPS.update(FLOW_OPS)
_LEN = {"imm": 2, "zp": 2, "zpx": 2, "zpy": 2, "izx": 2, "izy": 2, "izp": 2, "abs": 3, "absx": 3, "absy": 3,
        "rel": 2, "ind": 3, "iax": 3, "imp": 1, "acc": 1, "brk": 2}

_STORES = ("STA", "STX", "STY", "STZ")
_RMW_MEM = ("INC", "DEC", "ASL", "LSR", "ROL", "ROR", "TSB", "TRB")
_SHIFTS = ("ASL", "LSR", "ROL", "ROR")


def page_cross_applies(mn, mode):
    """Cruzamento de página custa +1 ciclo? (65C02) — leituras indexadas e shifts abs,X; nunca em
    stores nem em INC/DEC abs,X (7 fixos)."""
    if mode not in ("absx", "absy", "izy"):
        return False
    return mn not in _STORES and mn not in ("INC", "DEC")


def base_cycles(mn, mode):
    """Ciclos 65C02 por REGRA (sem extras de página/decimal/desvio tomado)."""
    if mn in FLOW_MNEMONICS:
        if mode == "rel":
            return 2
        if mn == "BRK":
            return 7
        if mn == "JMP":
            return {"abs": 3, "ind": 6, "iax": 6}[mode]
        return 6                                              # JSR, RTS, RTI
    if mode in ("imp", "acc"):
        if mn in ("PHA", "PHX", "PHY", "PHP"):
            return 3
        if mn in ("PLA", "PLX", "PLY", "PLP"):
            return 4
        return 2
    if mn in _RMW_MEM:
        if mn in ("TSB", "TRB"):
            return {"zp": 5, "abs": 6}[mode]
        return {"zp": 5, "zpx": 6, "abs": 6, "absx": 7 if mn in ("INC", "DEC") else 6}[mode]
    if mn in _STORES:
        return {"zp": 3, "zpx": 4, "zpy": 4, "abs": 4, "absx": 5, "absy": 5, "izx": 6, "izy": 6, "izp": 5}[mode]
    return {"imm": 2, "zp": 3, "zpx": 4, "zpy": 4, "abs": 4, "absx": 4, "absy": 4, "izx": 6, "izy": 5, "izp": 5}[mode]


class RefMem:
    def __init__(self, rng=None, value_fn=None, preset=None):
        self.m = dict(preset or {})
        self.rng = rng
        self.value_fn = value_fn or (lambda r: r.randrange(256))
        self.setup = []          # [(addr, val)] lidos antes de qualquer escrita
        self.written = {}        # addr RAM -> último valor escrito
        self.io_writes = []      # [(addr, val)] em ordem

    def read(self, addr):
        addr &= 0xFFFF
        if IO_LO <= addr <= IO_HI:
            return io_value(addr)
        if addr not in self.m:
            v = self.value_fn(self.rng) if self.rng is not None else 0
            self.m[addr] = v
            self.setup.append((addr, v))
        return self.m[addr]

    def write(self, addr, val):
        addr &= 0xFFFF
        val &= 0xFF
        if IO_LO <= addr <= IO_HI:
            self.io_writes.append((addr, val))
        else:
            self.m[addr] = val
            self.written[addr] = val


class RefCpu:
    def __init__(self, mem):
        self.mem = mem
        self.a = self.x = self.y = 0
        self.s = 0xFF
        self.c = self.v = self.d = self.n = self.z = self.i = self.b = 0
        self.cycles = 0
        self.pc = 0

    # ---- P empacotado: N V 1 B D I Z C ----
    def pack_p(self):
        return ((self.n << 7) | (self.v << 6) | 0x20 | (self.b << 4) | (self.d << 3) |
                (self.i << 2) | (self.z << 1) | self.c)

    def set_p(self, p):
        self.n, self.v, self.b = (p >> 7) & 1, (p >> 6) & 1, (p >> 4) & 1
        self.d, self.i, self.z, self.c = (p >> 3) & 1, (p >> 2) & 1, (p >> 1) & 1, p & 1

    def state(self):
        return dict(a=self.a, x=self.x, y=self.y, s=self.s, p=self.pack_p(), cycles=self.cycles)

    # ---- endereço efetivo ----
    def _zp_ptr(self, zp):
        lo = self.mem.read(zp & 0xFF)
        hi = self.mem.read((zp + 1) & 0xFF)          # wrap em página zero
        return lo | (hi << 8)

    def _ea(self, mode, op, mn):
        pc_pen = page_cross_applies(mn, mode)
        if mode == "zp":
            return op & 0xFF
        if mode == "zpx":
            return (op + self.x) & 0xFF
        if mode == "zpy":
            return (op + self.y) & 0xFF
        if mode == "abs":
            return op
        if mode in ("absx", "absy"):
            idx = self.x if mode == "absx" else self.y
            if pc_pen and ((op & 0xFF) + idx) > 0xFF:
                self.cycles += 1
            return (op + idx) & 0xFFFF
        if mode == "izx":
            return self._zp_ptr((op + self.x) & 0xFF)
        if mode == "izy":
            base = self._zp_ptr(op)
            if pc_pen and ((base & 0xFF) + self.y) > 0xFF:
                self.cycles += 1
            return (base + self.y) & 0xFFFF
        if mode == "izp":
            return self._zp_ptr(op)
        raise ValueError(mode)

    @staticmethod
    def _base_cycles(mn, mode):
        return base_cycles(mn, mode)

    # ---- flags ----
    def _set_nz(self, v):
        self.n = (v >> 7) & 1
        self.z = 1 if v == 0 else 0

    # ---- aritmética ----
    def _adc_bin(self, m):
        r = self.a + m + self.c
        self.v = 1 if (~(self.a ^ m) & (self.a ^ r) & 0x80) else 0
        self.c = 1 if r > 0xFF else 0
        self.a = r & 0xFF
        self._set_nz(self.a)

    def _adc_dec(self, m):
        a, c = self.a, self.c
        al = (a & 0x0F) + (m & 0x0F) + c
        if al >= 0x0A:
            al = ((al + 0x06) & 0x0F) + 0x10
        # V: Seq.2 — nibble alto com sinal
        sa = (a & 0xF0) - 256 if (a & 0x80) else (a & 0xF0)
        sm = (m & 0xF0) - 256 if (m & 0x80) else (m & 0xF0)
        sv = sa + sm + al
        self.v = 1 if (sv < -128 or sv > 127) else 0
        # Seq.1
        r = (a & 0xF0) + (m & 0xF0) + al
        if r >= 0xA0:
            r += 0x60
        self.c = 1 if r >= 0x100 else 0
        self.a = r & 0xFF
        self._set_nz(self.a)

    def _sbc_bin(self, m):
        r = self.a + (m ^ 0xFF) + self.c
        self.v = 1 if ((self.a ^ m) & (self.a ^ r) & 0x80) else 0
        self.c = 1 if r > 0xFF else 0
        self.a = r & 0xFF
        self._set_nz(self.a)

    def _sbc_dec(self, m):
        a, cin = self.a, self.c
        binr = a + (m ^ 0xFF) + cin
        self.v = 1 if ((a ^ m) & (a ^ binr) & 0x80) else 0
        self.c = 1 if binr > 0xFF else 0
        al = (a & 0x0F) - (m & 0x0F) + cin - 1
        if al < 0:
            al = ((al - 0x06) & 0x0F) - 0x10
        r = (a & 0xF0) - (m & 0xF0) + al
        if r < 0:
            r -= 0x60
        self.a = r & 0xFF
        self._set_nz(self.a)

    # ---- deslocamentos / INC / DEC: valor -> resultado (atualiza flags) ----
    def _rmw(self, mn, v):
        if mn == "INC":
            r = (v + 1) & 0xFF
        elif mn == "DEC":
            r = (v - 1) & 0xFF
        elif mn == "ASL":
            self.c = (v >> 7) & 1
            r = (v << 1) & 0xFF
        elif mn == "LSR":
            self.c = v & 1
            r = v >> 1
        elif mn == "ROL":
            r = ((v << 1) | self.c) & 0xFF
            self.c = (v >> 7) & 1
        elif mn == "ROR":
            r = (v >> 1) | (self.c << 7)
            self.c = v & 1
        else:
            raise ValueError(mn)
        self._set_nz(r)
        return r

    def _compare(self, reg, m):
        t = (reg - m) & 0xFF
        self.c = 1 if reg >= m else 0
        self._set_nz(t)

    def _push(self, v):
        self.mem.write(0x100 | self.s, v)
        self.s = (self.s - 1) & 0xFF

    def _pull(self):
        self.s = (self.s + 1) & 0xFF
        return self.mem.read(0x100 | self.s)

    def _implied(self, mn):
        if mn in ("INX", "INY", "DEX", "DEY"):
            reg = {"INX": "x", "INY": "y", "DEX": "x", "DEY": "y"}[mn]
            d = 1 if mn in ("INX", "INY") else -1
            setattr(self, reg, (getattr(self, reg) + d) & 0xFF)
            self._set_nz(getattr(self, reg))
        elif mn in ("TAX", "TAY", "TXA", "TYA", "TSX"):
            dst, src = {"TAX": ("x", "a"), "TAY": ("y", "a"), "TXA": ("a", "x"), "TYA": ("a", "y"),
                        "TSX": ("x", "s")}[mn]
            setattr(self, dst, getattr(self, src))
            self._set_nz(getattr(self, dst))
        elif mn == "TXS":
            self.s = self.x
        elif mn == "CLC":
            self.c = 0
        elif mn == "SEC":
            self.c = 1
        elif mn == "CLI":
            self.i = 0
        elif mn == "SEI":
            self.i = 1
        elif mn == "CLV":
            self.v = 0
        elif mn == "CLD":
            self.d = 0
        elif mn == "SED":
            self.d = 1
        elif mn == "NOP":
            pass
        elif mn in ("PHA", "PHX", "PHY"):
            self._push({"PHA": self.a, "PHX": self.x, "PHY": self.y}[mn])
        elif mn == "PHP":
            self._push(self.pack_p() | 0x10)               # B=1 no P empilhado
        elif mn in ("PLA", "PLX", "PLY"):
            v = self._pull()
            setattr(self, {"PLA": "a", "PLX": "x", "PLY": "y"}[mn], v)
            self._set_nz(v)
        elif mn == "PLP":
            self.set_p(self._pull())
            self.b = 0                                      # PLP ignora o bit B
        else:
            raise ValueError(mn)

    def exec_insn(self, opcode, operand):
        """Executa uma instrução SEQUENCIAL (sem fluxo de controle)."""
        mn, mode = REF_OPS[opcode]
        self.cycles += base_cycles(mn, mode)
        if mode == "imp":
            self._implied(mn)
            return
        if mode == "acc":
            self.a = self._rmw(mn, self.a)
            return
        if mn in _STORES:
            ea = self._ea(mode, operand, mn)
            val = {"STA": self.a, "STX": self.x, "STY": self.y, "STZ": 0}[mn]
            self.mem.write(ea, val)
            return
        if mn in _RMW_MEM:
            ea = self._ea(mode, operand, mn)
            m = self.mem.read(ea)
            if mn in ("TSB", "TRB"):
                self.z = 1 if (self.a & m) == 0 else 0
                self.mem.write(ea, (m | self.a) if mn == "TSB" else (m & ~self.a & 0xFF))
            else:
                self.mem.write(ea, self._rmw(mn, m))
            return
        m = operand & 0xFF if mode == "imm" else self.mem.read(self._ea(mode, operand, mn))
        if mn in ("LDA", "LDX", "LDY"):
            setattr(self, mn[2].lower(), m)
            self._set_nz(m)
        elif mn == "ORA":
            self.a |= m
            self._set_nz(self.a)
        elif mn == "AND":
            self.a &= m
            self._set_nz(self.a)
        elif mn == "EOR":
            self.a ^= m
            self._set_nz(self.a)
        elif mn == "ADC":
            if self.d:
                self.cycles += 1
                self._adc_dec(m)
            else:
                self._adc_bin(m)
        elif mn == "SBC":
            if self.d:
                self.cycles += 1
                self._sbc_dec(m)
            else:
                self._sbc_bin(m)
        elif mn in ("CMP", "CPX", "CPY"):
            self._compare({"CMP": self.a, "CPX": self.x, "CPY": self.y}[mn], m)
        elif mn == "BIT":
            self.z = 1 if (self.a & m) == 0 else 0
            if mode != "imm":                               # BIT #imm (65C02) só altera Z
                self.n = (m >> 7) & 1
                self.v = (m >> 6) & 1
        else:
            raise ValueError(mn)

    # ---- fluxo de controle ----
    def _flag(self, f):
        return {"N": self.n, "V": self.v, "C": self.c, "Z": self.z}[f]

    def exec_flow(self, mn, mode, operand, addr):
        """Executa um desvio/salto/JSR/RTS/BRK/RTI em 'addr' e deixa o resultado em self.pc."""
        self.cycles += base_cycles(mn, mode)
        nxt = (addr + _LEN[mode]) & 0xFFFF
        if mode == "rel":
            taken = True if mn == "BRA" else (self._flag(BR_COND[mn][0]) == BR_COND[mn][1])
            if taken:
                off = operand - 256 if operand & 0x80 else operand
                tgt = (nxt + off) & 0xFFFF
                self.cycles += 1
                if (tgt & 0xFF00) != (nxt & 0xFF00):
                    self.cycles += 1
                self.pc = tgt
            else:
                self.pc = nxt
        elif mn == "JMP":
            if mode == "abs":
                self.pc = operand
            else:
                ea = operand if mode == "ind" else (operand + self.x) & 0xFFFF
                lo = self.mem.read(ea)
                hi = self.mem.read((ea + 1) & 0xFFFF)       # 65C02: sem o bug de wrap de página
                self.pc = lo | (hi << 8)
        elif mn == "JSR":
            ret = (addr + 2) & 0xFFFF                        # endereço do último byte do JSR
            self._push(ret >> 8)
            self._push(ret & 0xFF)
            self.pc = operand
        elif mn == "RTS":
            lo = self._pull()
            hi = self._pull()
            self.pc = (((hi << 8) | lo) + 1) & 0xFFFF
        elif mn == "BRK":
            self._push(nxt >> 8)                             # empilha addr+2 (RTI não soma 1)
            self._push(nxt & 0xFF)
            self._push(self.pack_p() | 0x10)                 # B=1
            self.i = 1
            self.d = 0                                       # 65C02 limpa D
            lo = self.mem.read(0xFFFE)
            hi = self.mem.read(0xFFFF)
            self.pc = lo | (hi << 8)
        elif mn == "RTI":
            self.set_p(self._pull())
            self.b = 0
            lo = self._pull()
            hi = self._pull()
            self.pc = (hi << 8) | lo
        else:
            raise ValueError(mn)

    def run_program(self, image, org, entries, entry_pc, budget, smc_operands=(), roots=None):
        """Executa uma imagem com fluxo de controle até uma FRONTEIRA DE BLOCO.

        Fronteira = instrução de fluxo, ou próximo PC sequencial que é uma RAIZ (início de função C) ou sai da
        imagem. Em cada fronteira (mesma ordem do código traduzido: teste de evento e depois despacho):
          1. ciclos >= budget  -> ('yield', pc)
          2. pc fora de 'entries' (todo líder é despachável) -> ('unresolved', pc)
        'roots' padrão = entries (fase 1: um bloco por função). Na fase 2 só as raízes das rotinas são fronteiras:
        cair de um bloco no seguinte DENTRO da mesma rotina não testa evento.
        """
        end = org + len(image)
        entries = set(entries)
        roots = entries if roots is None else set(roots)
        smc = set(smc_operands)       # bytes de operando IMEDIATO lidos da MEMÓRIA a cada execução (param_operand)
        self.pc = entry_pc
        while True:
            addr = self.pc
            opcode = image[addr - org]
            if opcode not in REF_OPS:
                raise ValueError("opcode $%02X em $%04X fora do subconjunto de referência" % (opcode, addr))
            mn, mode = REF_OPS[opcode]
            n = _LEN[mode]
            if n == 1:
                operand = None
            elif n == 2:
                operand = self.mem.read(addr + 1) if (mode == "imm" and (addr + 1) in smc) else image[addr - org + 1]
            else:
                operand = image[addr - org + 1] | (image[addr - org + 2] << 8)
            flow = mn in FLOW_MNEMONICS
            if flow:
                self.exec_flow(mn, mode, operand, addr)
            else:
                self.exec_insn(opcode, operand)
                self.pc = (addr + n) & 0xFFFF
            if flow or self.pc in roots or not (org <= self.pc < end):
                if self.cycles >= budget:
                    return ("yield", self.pc)
                if self.pc not in entries:
                    return ("unresolved", self.pc)

    def run(self, code):
        """Executa um bloco reto de bytes de código (sem fluxo de controle)."""
        off = 0
        while off < len(code):
            opcode = code[off]
            if opcode not in REF_OPS:
                raise ValueError("opcode $%02X fora do subconjunto de referência" % opcode)
            mn, mode = REF_OPS[opcode]
            if mn in FLOW_MNEMONICS:
                raise ValueError("run() é só para blocos retos; use run_program()")
            n = _LEN[mode]
            if n == 1:
                operand = None
            elif n == 2:
                operand = code[off + 1]
            else:
                operand = code[off + 1] | (code[off + 2] << 8)
            self.exec_insn(opcode, operand)
            off += n
