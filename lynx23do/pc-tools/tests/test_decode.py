"""Decoder do lynx2c vs. tabela de referência DERIVADA do padrão de bits (independente do JSON)."""
import unittest

from lynx2c.decode import (decode_block, decode_one, UnsupportedOpcode, TruncatedInstruction)
from lynx2c.optable import Optable
from lynxtrace.core65c02 import REF_OPS, _LEN


class TestOptableVsReference(unittest.TestCase):
    def test_same_opcode_set(self):
        self.assertEqual(set(Optable().by_opcode), set(REF_OPS))

    def test_mnemonic_mode_length_match(self):
        t = Optable()
        for opc, (mn, mode) in REF_OPS.items():
            info = t.get(opc)
            self.assertEqual((info.mnemonic, info.mode, info.length), (mn, mode, _LEN[mode]),
                             "opcode $%02X" % opc)

    def test_cycles_match_reference_formula(self):
        from lynxtrace.core65c02 import RefCpu
        t = Optable()
        for opc, (mn, mode) in REF_OPS.items():
            self.assertEqual(t.get(opc).cycles, RefCpu._base_cycles(mn, mode), "opcode $%02X" % opc)

    def test_page_cross_flag(self):
        for opc, (mn, mode) in REF_OPS.items():
            expect = mn != "STA" and mode in ("absx", "absy", "izy")
            self.assertEqual(Optable().get(opc).page_cross, expect, "opcode $%02X" % opc)


class TestDecode(unittest.TestCase):
    def test_sequence(self):
        insns = decode_block(bytes([0xA9, 0x01, 0x69, 0x02, 0x8D, 0x91, 0xFC]), 0x0200)
        self.assertEqual([i.text() for i in insns], ["LDA #$01", "ADC #$02", "STA $FC91"])
        self.assertEqual([i.addr for i in insns], [0x200, 0x202, 0x204])
        self.assertEqual(insns[-1].next_addr, 0x207)

    def test_little_endian_operand(self):
        self.assertEqual(decode_one(bytes([0xAD, 0x34, 0x12]), 0, 0).operand, 0x1234)

    def test_unsupported_is_explicit(self):
        with self.assertRaises(UnsupportedOpcode) as cm:
            decode_block(bytes([0xEA]), 0x0300)    # NOP: ainda não suportado
        self.assertIn("$EA", str(cm.exception))
        self.assertIn("$0300", str(cm.exception))

    def test_sta_immediate_is_not_sta(self):
        with self.assertRaises(UnsupportedOpcode):
            decode_block(bytes([0x89, 0x00]), 0)   # $89 = BIT # no 65C02

    def test_truncated(self):
        with self.assertRaises(TruncatedInstruction):
            decode_block(bytes([0xAD, 0x34]), 0)


if __name__ == "__main__":
    unittest.main()
