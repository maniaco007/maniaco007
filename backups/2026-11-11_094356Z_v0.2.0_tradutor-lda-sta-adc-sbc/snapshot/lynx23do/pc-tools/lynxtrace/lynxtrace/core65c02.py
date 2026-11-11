"""Núcleo de referência 65C02 — escrito de forma INDEPENDENTE do tradutor.

Independência deliberada (para o teste diferencial ter valor):
  - tabela de opcodes DERIVADA do padrão de bits 'aaabbbcc' do 6502 (não copiada
    do optable.json do lynx2c);
  - modos de endereçamento e ciclos calculados por fórmula, não por tabela;
  - ADC/SBC decimais escritos em Python com aritmética de inteiros, a partir da
    descrição de Bruce Clark (mesma FONTE da semântica que o C, mas código distinto);
  - cobertura extra por PROPRIEDADE para BCD válido (test_reference_core.py).

Modelo de memória (espelha o harness C):
  - RAM: dict esparso; 1ª leitura de endereço nunca escrito sorteia um valor e o
    REGISTRA em 'setup' (o harness C recebe esse setup);
  - $FC00-$FDFF: E/S — leitura devolve io_value(addr); escritas vão para 'io_writes'
    (ordem preservada); $FE00-$FFFF: RAM por baixo (igual a lx_mem.c).
"""

IO_LO, IO_HI = 0xFC00, 0xFDFF


def io_value(addr):
    """Valor lido de E/S (igual aos stubs do harness C). DIFERE por região (Suzy x Mikey),
    para que um acesso roteado ao chip errado seja detectado pelo teste diferencial."""
    if addr <= 0xFCFF:
        return (addr * 7 + 13) & 0xFF      # Suzy  $FC00-$FCFF
    return (addr * 11 + 5) & 0xFF          # Mikey $FD00-$FDFF


# ---- tabela de opcodes derivada do padrão aaabbbcc (grupo 1, cc=01) -----------------
_GROUP1 = {"ADC": 0b011, "STA": 0b100, "LDA": 0b101, "SBC": 0b111}
_BBB_MODE = {0b000: "izx", 0b001: "zp", 0b010: "imm", 0b011: "abs",
             0b100: "izy", 0b101: "zpx", 0b110: "absy", 0b111: "absx"}


def build_ref_table():
    t = {}
    for mn, aaa in _GROUP1.items():
        for bbb, mode in _BBB_MODE.items():
            if mn == "STA" and mode == "imm":
                continue                      # $89 em 65C02 é BIT #, não STA #
            t[(aaa << 5) | (bbb << 2) | 0b01] = (mn, mode)
        t[(aaa << 5) | 0x12] = (mn, "izp")    # 65C02: (zp) = aaa 100 10
    return t


REF_OPS = build_ref_table()
_LEN = {"imm": 2, "zp": 2, "zpx": 2, "izx": 2, "izy": 2, "izp": 2, "abs": 3, "absx": 3, "absy": 3}


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

    def _ea(self, mode, op, is_read):
        if mode == "zp":
            return op & 0xFF
        if mode == "zpx":
            return (op + self.x) & 0xFF
        if mode == "abs":
            return op
        if mode in ("absx", "absy"):
            idx = self.x if mode == "absx" else self.y
            if is_read and ((op & 0xFF) + idx) > 0xFF:
                self.cycles += 1
            return (op + idx) & 0xFFFF
        if mode == "izx":
            return self._zp_ptr((op + self.x) & 0xFF)
        if mode == "izy":
            base = self._zp_ptr(op)
            if is_read and ((base & 0xFF) + self.y) > 0xFF:
                self.cycles += 1
            return (base + self.y) & 0xFFFF
        if mode == "izp":
            return self._zp_ptr(op)
        raise ValueError(mode)

    @staticmethod
    def _base_cycles(mn, mode):
        if mn == "STA":
            return {"zp": 3, "zpx": 4, "abs": 4, "absx": 5, "absy": 5, "izx": 6, "izy": 6, "izp": 5}[mode]
        return {"imm": 2, "zp": 3, "zpx": 4, "abs": 4, "absx": 4, "absy": 4, "izx": 6, "izy": 5, "izp": 5}[mode]

    # ---- operações ----
    def _set_nz(self, v):
        self.n = (v >> 7) & 1
        self.z = 1 if v == 0 else 0

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

    def exec_insn(self, opcode, operand):
        mn, mode = REF_OPS[opcode]
        self.cycles += self._base_cycles(mn, mode)
        if mn == "STA":
            ea = self._ea(mode, operand, False)
            self.mem.write(ea, self.a)
            return
        if mode == "imm":
            m = operand & 0xFF
        else:
            m = self.mem.read(self._ea(mode, operand, True))
        if mn == "LDA":
            self.a = m
            self._set_nz(m)
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

    def run(self, code):
        """Executa um bloco reto de bytes de código (sem fluxo de controle)."""
        off = 0
        while off < len(code):
            opcode = code[off]
            if opcode not in REF_OPS:
                raise ValueError("opcode $%02X fora do subconjunto de referência" % opcode)
            mode = REF_OPS[opcode][1]
            n = _LEN[mode]
            if n == 1:
                operand = None
            elif n == 2:
                operand = code[off + 1]
            else:
                operand = code[off + 1] | (code[off + 2] << 8)
            self.exec_insn(opcode, operand)
            off += n
