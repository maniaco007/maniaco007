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
        self.assertEqual(len(REF_OPS), 35)


if __name__ == "__main__":
    unittest.main()
