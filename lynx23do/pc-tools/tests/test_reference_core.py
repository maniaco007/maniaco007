"""Valida o PRÓPRIO núcleo de referência com oráculos independentes (propriedades).

Sem isto, o teste diferencial só provaria que dois códigos escritos pela mesma
pessoa concordam. Aqui o oráculo é aritmética decimal/binária elementar.
"""
import random
import unittest

from lynxtrace.core65c02 import RefCpu, RefMem, REF_OPS


def cpu(a=0, c=0, d=0):
    r = RefCpu(RefMem())
    r.a, r.c, r.d = a, c, d
    return r


def bcd(v):               # 0..99 -> byte BCD
    return ((v // 10) << 4) | (v % 10)


def dec(b):               # byte BCD válido -> 0..99
    return (b >> 4) * 10 + (b & 0xF)


class TestBinary(unittest.TestCase):
    def test_adc_exhaustive_against_python_int_math(self):
        for a in range(256):
            for m in range(256):
                for c in (0, 1):
                    r = cpu(a, c); r._adc_bin(m)
                    s = a + m + c
                    self.assertEqual(r.a, s & 0xFF)
                    self.assertEqual(r.c, 1 if s > 255 else 0)
                    sa = a - 256 if a >= 128 else a
                    sm = m - 256 if m >= 128 else m
                    ss = sa + sm + c
                    self.assertEqual(r.v, 1 if (ss < -128 or ss > 127) else 0)
                    self.assertEqual(r.n, (r.a >> 7) & 1)
                    self.assertEqual(r.z, 1 if r.a == 0 else 0)

    def test_sbc_exhaustive_against_python_int_math(self):
        for a in range(256):
            for m in range(256):
                for c in (0, 1):
                    r = cpu(a, c); r._sbc_bin(m)
                    s = a - m - (1 - c)
                    self.assertEqual(r.a, s & 0xFF)
                    self.assertEqual(r.c, 1 if s >= 0 else 0)
                    sa = a - 256 if a >= 128 else a
                    sm = m - 256 if m >= 128 else m
                    ss = sa - sm - (1 - c)
                    self.assertEqual(r.v, 1 if (ss < -128 or ss > 127) else 0)


class TestDecimalValidBCD(unittest.TestCase):
    """Para operandos BCD VÁLIDOS, o resultado é a aritmética decimal comum."""

    def test_adc_decimal(self):
        for x in range(100):
            for y in range(100):
                for c in (0, 1):
                    r = cpu(bcd(x), c, 1); r._adc_dec(bcd(y))
                    s = x + y + c
                    self.assertEqual(r.a, bcd(s % 100), (x, y, c))
                    self.assertEqual(r.c, 1 if s >= 100 else 0, (x, y, c))
                    self.assertEqual(r.z, 1 if r.a == 0 else 0)
                    self.assertEqual(r.n, (r.a >> 7) & 1)

    def test_sbc_decimal(self):
        for x in range(100):
            for y in range(100):
                for c in (0, 1):
                    r = cpu(bcd(x), c, 1); r._sbc_dec(bcd(y))
                    s = x - y - (1 - c)
                    self.assertEqual(r.a, bcd(s % 100), (x, y, c))
                    self.assertEqual(r.c, 1 if s >= 0 else 0, (x, y, c))
                    self.assertEqual(r.z, 1 if r.a == 0 else 0)


class TestCyclesAndModes(unittest.TestCase):
    def test_decimal_extra_cycle_and_page_cross(self):
        m = RefMem(preset={0x12FF + 1: 5})
        r = RefCpu(m); r.x = 1; r.d = 1
        r.run(bytes([0x7D, 0xFF, 0x12]))          # ADC $12FF,X : 4 +1 (página) +1 (decimal)
        self.assertEqual(r.cycles, 6)

    def test_sta_indexed_has_no_page_cross_penalty(self):
        r = RefCpu(RefMem()); r.x = 0xFF
        r.run(bytes([0x9D, 0xFF, 0x12]))          # STA $12FF,X = 5 fixo
        self.assertEqual(r.cycles, 5)

    def test_zero_page_pointer_wraps(self):
        m = RefMem(preset={0xFF: 0x34, 0x00: 0x12, 0x1234: 0x77})
        r = RefCpu(m)
        r.run(bytes([0xB2, 0xFF]))                # LDA ($FF): ponteiro = [$FF]|[$00]<<8
        self.assertEqual(r.a, 0x77)

    def test_io_read_and_write_log(self):
        r = RefCpu(RefMem())
        r.run(bytes([0xAD, 0x91, 0xFC, 0x8D, 0x91, 0xFC]))   # LDA $FC91 ; STA $FC91
        self.assertEqual(r.mem.io_writes, [(0xFC91, r.a)])

    def test_opcode_table_shape(self):
        self.assertEqual(len(REF_OPS), 178)


class TestControlFlow(unittest.TestCase):
    """Semântica de fluxo verificada à mão (não pelo próprio código de referência)."""

    def flow(self, mn, mode, operand, addr, **regs):
        r = RefCpu(RefMem())
        for k, v in regs.items():
            setattr(r, k, v)
        r.exec_flow(mn, mode, operand, addr)
        return r

    def test_branch_cycles(self):
        self.assertEqual(self.flow("BNE", "rel", 0x10, 0x0300, z=0).cycles, 3)       # tomado, mesma página
        self.assertEqual(self.flow("BNE", "rel", 0x10, 0x0300, z=1).cycles, 2)       # não tomado
        self.assertEqual(self.flow("BNE", "rel", 0x10, 0x03F0, z=0).cycles, 4)       # tomado, cruza página
        self.assertEqual(self.flow("BRA", "rel", 0x10, 0x03F0).cycles, 4)

    def test_branch_targets(self):
        self.assertEqual(self.flow("BEQ", "rel", 0xFE, 0x0300, z=1).pc, 0x0300)       # -2: salta para si mesmo
        self.assertEqual(self.flow("BCC", "rel", 0x05, 0x0300, c=0).pc, 0x0307)
        self.assertEqual(self.flow("BCC", "rel", 0x05, 0x0300, c=1).pc, 0x0302)

    def test_all_branch_conditions(self):
        cases = {"BPL": ("n", 0), "BMI": ("n", 1), "BVC": ("v", 0), "BVS": ("v", 1),
                 "BCC": ("c", 0), "BCS": ("c", 1), "BNE": ("z", 0), "BEQ": ("z", 1)}
        for mn, (f, val) in cases.items():
            self.assertEqual(self.flow(mn, "rel", 0x10, 0x0300, **{f: val}).pc, 0x0312, mn)
            self.assertEqual(self.flow(mn, "rel", 0x10, 0x0300, **{f: 1 - val}).pc, 0x0302, mn)

    def test_jsr_pushes_last_byte_address_and_rts_returns_after(self):
        r = RefCpu(RefMem()); r.s = 0xFF
        r.exec_flow("JSR", "abs", 0x0400, 0x0300)
        self.assertEqual((r.pc, r.s, r.cycles), (0x0400, 0xFD, 6))
        self.assertEqual(r.mem.written, {0x01FF: 0x03, 0x01FE: 0x02})                # $0302 = último byte do JSR
        r.exec_flow("RTS", "imp", None, 0x0400)
        self.assertEqual((r.pc, r.s, r.cycles), (0x0303, 0xFF, 12))

    def test_jmp_indirect_has_no_page_wrap_bug(self):
        m = RefMem(preset={0x10FF: 0x34, 0x1100: 0x12, 0x1000: 0xEE})
        r = RefCpu(m); r.exec_flow("JMP", "ind", 0x10FF, 0x0300)
        self.assertEqual((r.pc, r.cycles), (0x1234, 6))

    def test_jmp_indexed_indirect(self):
        m = RefMem(preset={0x2002: 0x78, 0x2003: 0x56})
        r = RefCpu(m); r.x = 2; r.exec_flow("JMP", "iax", 0x2000, 0x0300)
        self.assertEqual((r.pc, r.cycles), (0x5678, 6))

    def test_run_program_stops_at_budget_and_at_unresolved(self):
        img = bytes([0x80, 0xFE])                                                    # BRA * (laço infinito)
        r = RefCpu(RefMem())
        self.assertEqual(r.run_program(img, 0x300, {0x300}, 0x300, 100), ("yield", 0x300))
        self.assertEqual(r.cycles, 102)                                              # 34 iterações x 3 ciclos
        r = RefCpu(RefMem())
        self.assertEqual(r.run_program(bytes([0x4C, 0x00, 0x90]), 0x300, {0x300}, 0x300, 100),
                         ("unresolved", 0x9000))


class TestExtendedSet(unittest.TestCase):
    """Semântica do conjunto estendido verificada contra aritmética Python elementar / valores à mão."""

    def cpu(self, **regs):
        r = RefCpu(RefMem(preset=regs.pop("mem", {})))
        for k, v in regs.items():
            setattr(r, k, v)
        return r

    def test_cmp_exhaustive(self):
        for reg in range(256):
            for m in range(256):
                r = self.cpu(a=reg); r._compare(reg, m)
                self.assertEqual(r.c, 1 if reg >= m else 0)
                self.assertEqual(r.z, 1 if reg == m else 0)
                self.assertEqual(r.n, ((reg - m) & 0xFF) >> 7)

    def test_shifts_exhaustive(self):
        for v in range(256):
            for c in (0, 1):
                r = self.cpu(c=c); out = r._rmw("ASL", v)
                self.assertEqual((out, r.c), ((v << 1) & 0xFF, v >> 7))
                r = self.cpu(c=c); out = r._rmw("LSR", v)
                self.assertEqual((out, r.c, r.n), (v >> 1, v & 1, 0))
                r = self.cpu(c=c); out = r._rmw("ROL", v)
                self.assertEqual((out, r.c), (((v << 1) | c) & 0xFF, v >> 7))
                r = self.cpu(c=c); out = r._rmw("ROR", v)
                self.assertEqual((out, r.c), ((v >> 1) | (c << 7), v & 1))
                for mn, d in (("INC", 1), ("DEC", -1)):
                    r = self.cpu(); out = r._rmw(mn, v)
                    self.assertEqual((out, r.z, r.n), ((v + d) & 0xFF, 1 if out == 0 else 0, out >> 7))

    def test_cmp_examples(self):
        for imm, (z, c, n) in {5: (1, 1, 0), 6: (0, 0, 1), 4: (0, 1, 0)}.items():
            r = self.cpu(a=5); r.exec_insn(0xC9, imm)
            self.assertEqual((r.z, r.c, r.n), (z, c, n))

    def test_bit_immediate_only_changes_z(self):
        r = self.cpu(a=0x0F, n=1, v=1); r.exec_insn(0x89, 0xF0)
        self.assertEqual((r.z, r.n, r.v), (1, 1, 1))
        r = self.cpu(a=0x0F, mem={0x10: 0xC0}); r.exec_insn(0x24, 0x10)       # BIT zp copia bits 7 e 6
        self.assertEqual((r.z, r.n, r.v), (1, 1, 1))

    def test_tsb_trb(self):
        r = self.cpu(a=0x0F, mem={0x10: 0x3C}); r.exec_insn(0x04, 0x10)
        self.assertEqual((r.z, r.mem.written[0x10]), (0, 0x3F))
        r = self.cpu(a=0x0F, mem={0x10: 0x3C}); r.exec_insn(0x14, 0x10)
        self.assertEqual((r.z, r.mem.written[0x10]), (0, 0x30))
        r = self.cpu(a=0x0F, mem={0x10: 0xF0}); r.exec_insn(0x04, 0x10)
        self.assertEqual(r.z, 1)

    def test_php_plp_b_flag(self):
        r = self.cpu(c=1, z=1, s=0xFF); r.exec_insn(0x08, None)               # PHP
        self.assertEqual(r.mem.written[0x1FF], 0x20 | 0x10 | 0x02 | 0x01)     # bits 5 e 4 (B) sempre 1 no push
        r = self.cpu(s=0xFE, mem={0x1FF: 0xFF}); r.exec_insn(0x28, None)      # PLP de $FF
        self.assertEqual((r.pack_p(), r.b), (0xEF, 0))                       # B ignorado ao desempilhar

    def test_brk_and_rti(self):
        r = self.cpu(s=0xFF, c=1, z=1, d=1, mem={0xFFFE: 0x34, 0xFFFF: 0x12})
        r.exec_flow("BRK", "brk", 0xAA, 0x0300)
        self.assertEqual((r.pc, r.s, r.i, r.d, r.cycles), (0x1234, 0xFC, 1, 0, 7))
        self.assertEqual(r.mem.written, {0x1FF: 0x03, 0x1FE: 0x02, 0x1FD: 0x20 | 0x10 | 0x08 | 0x02 | 0x01})
        r.exec_flow("RTI", "imp", None, 0x1234)
        self.assertEqual((r.pc, r.s, r.d, r.i, r.b, r.cycles), (0x0302, 0xFF, 1, 0, 0, 13))   # sem +1; P restaurado

    def test_inc_dec_absx_fixed_seven_shifts_page_cross(self):
        r = self.cpu(x=1, mem={0x1300: 5}); r.run(bytes([0xFE, 0xFF, 0x12]))   # INC $12FF,X
        self.assertEqual(r.cycles, 7)
        r = self.cpu(x=1, mem={0x1300: 5}); r.run(bytes([0x1E, 0xFF, 0x12]))   # ASL $12FF,X (cruza)
        self.assertEqual(r.cycles, 7)
        r = self.cpu(x=1, mem={0x1210: 5}); r.run(bytes([0x1E, 0x0F, 0x12]))   # ASL $120F,X (não cruza)
        self.assertEqual(r.cycles, 6)

    def test_zero_page_y_wraps(self):
        r = self.cpu(y=2, mem={0x01: 0x99}); r.run(bytes([0xB6, 0xFF]))       # LDX $FF,Y -> $01
        self.assertEqual(r.x, 0x99)

    def test_transfers_and_stack_pointer(self):
        r = self.cpu(a=0x80); r.run(bytes([0xAA, 0xA8]))                      # TAX, TAY
        self.assertEqual((r.x, r.y, r.n, r.z), (0x80, 0x80, 1, 0))
        r = self.cpu(x=0x00, s=0x55); r.run(bytes([0x9A]))                    # TXS não toca flags
        self.assertEqual((r.s, r.z, r.n), (0x00, 0, 0))
        r = self.cpu(s=0x00); r.run(bytes([0xBA]))                            # TSX
        self.assertEqual((r.x, r.z), (0, 1))

    def test_stz_and_nop(self):
        r = self.cpu(); r.run(bytes([0x64, 0x10, 0xEA]))
        self.assertEqual((r.mem.written, r.cycles), ({0x10: 0}, 5))


if __name__ == "__main__":
    unittest.main()
