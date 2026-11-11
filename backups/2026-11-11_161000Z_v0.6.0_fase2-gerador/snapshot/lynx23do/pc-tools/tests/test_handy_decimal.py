"""Segunda implementação INDEPENDENTE do ADC/SBC decimal: o algoritmo do Handy (transcrito do macro xADC/xSBC de
c6502mak.h, lido como dado) comparado EXAUSTIVAMENTE (A x M x C = 131 072 casos por operação) com a referência própria.

Resultado esperado e fixado aqui: concordância TOTAL (A, C, V, N, Z) quando os operandos são BCD válidos; qualquer
divergência só pode ocorrer com operando BCD inválido (nibble > 9), e o conjunto exato dessas divergências é medido e fixado.
"""
import unittest

from lynxtrace.core65c02 import RefCpu, RefMem


def handy_adc_dec(a, value, c):
    """Transcrição do ramo decimal de xADC (Handy). Retorna (A, C, V, N, Z)."""
    lo = (a & 0x0F) + (value & 0x0F) + c
    hi = (a & 0xF0) + (value & 0xF0)
    v = cc = 0
    if lo > 0x09:
        hi += 0x10
        lo += 0x06
    if ~(a ^ value) & (a ^ hi) & 0x80:
        v = 1
    if hi > 0x90:
        hi += 0x60
    if hi & 0xFF00:
        cc = 1
    r = ((lo & 0x0F) + (hi & 0xF0)) & 0xFF
    return r, cc, v, (r >> 7) & 1, 1 if r == 0 else 0


def handy_sbc_dec(a, value, carry):
    """Transcrição do ramo decimal de xSBC (Handy). Retorna (A, C, V, N, Z)."""
    c = 0 if carry else 1
    s = a - value - c
    lo = (a & 0x0F) - (value & 0x0F) - c
    hi = (a & 0xF0) - (value & 0xF0)
    v = cc = 0
    if (a ^ value) & (a ^ s) & 0x80:
        v = 1
    if lo & 0xF0:
        lo -= 6
    if lo & 0x80:
        hi -= 0x10
    if hi & 0x0F00:
        hi -= 0x60
    if (s & 0xFF00) == 0:
        cc = 1
    r = ((lo & 0x0F) + (hi & 0xF0)) & 0xFF
    return r, cc, v, (r >> 7) & 1, 1 if r == 0 else 0


def ours(op, a, m, c):
    r = RefCpu(RefMem())
    r.a, r.c, r.d = a, c, 1
    getattr(r, "_adc_dec" if op == "adc" else "_sbc_dec")(m)
    return r.a, r.c, r.v, r.n, r.z


def valid_bcd(x):
    return (x & 0x0F) <= 9 and (x >> 4) <= 9


class TestHandyDecimal(unittest.TestCase):
    def mismatches(self, op, fn):
        valid, invalid = [], []
        for a in range(256):
            for m in range(256):
                for c in (0, 1):
                    if ours(op, a, m, c) != fn(a, m, c):
                        (valid if valid_bcd(a) and valid_bcd(m) else invalid).append((a, m, c))
        return valid, invalid

    def test_adc_agrees_fully_on_valid_bcd(self):
        valid, invalid = self.mismatches("adc", handy_adc_dec)
        self.assertEqual(valid, [], "divergência com operandos BCD VÁLIDOS: %s" % valid[:5])
        self.last_adc_invalid = len(invalid)

    def test_sbc_agrees_fully_on_valid_bcd(self):
        valid, invalid = self.mismatches("sbc", handy_sbc_dec)
        self.assertEqual(valid, [], "divergência com operandos BCD VÁLIDOS: %s" % valid[:5])

    def test_invalid_bcd_divergence_is_pinned(self):
        # Medido uma vez e fixado: qualquer mudança (nossa ou do que se espera do Handy) passa a ser explícita.
        _, inv_adc = self.mismatches("adc", handy_adc_dec)
        _, inv_sbc = self.mismatches("sbc", handy_sbc_dec)
        self.assertEqual((len(inv_adc), len(inv_sbc)), EXPECTED_INVALID_DIVERGENCES)


EXPECTED_INVALID_DIVERGENCES = (0, 0)      # preenchido após a primeira medição (ver docs/09)

if __name__ == "__main__":
    unittest.main()
