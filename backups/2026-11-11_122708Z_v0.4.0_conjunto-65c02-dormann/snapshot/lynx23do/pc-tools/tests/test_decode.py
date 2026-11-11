"""Decoder do lynx2c vs. tabela de referência DERIVADA do padrão de bits (independente do JSON)."""
import unittest

from lynx2c.decode import (decode_block, decode_one, UnsupportedOpcode, TruncatedInstruction)
from lynx2c.optable import Optable
from lynxtrace.core65c02 import REF_OPS, _LEN, base_cycles, page_cross_applies


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
        t = Optable()
        for opc, (mn, mode) in REF_OPS.items():
            self.assertEqual(t.get(opc).cycles, base_cycles(mn, mode), "opcode $%02X" % opc)

    def test_page_cross_flag(self):
        for opc, (mn, mode) in REF_OPS.items():
            self.assertEqual(Optable().get(opc).page_cross, page_cross_applies(mn, mode), "opcode $%02X" % opc)

    def test_known_opcodes_from_the_datasheet(self):
        """Conferência pontual com opcodes bem conhecidos (fonte: folha de dados do 6502/65C02)."""
        known = {0xEA: "NOP", 0x48: "PHA", 0x68: "PLA", 0x08: "PHP", 0x28: "PLP", 0x9A: "TXS", 0xBA: "TSX",
                 0xAA: "TAX", 0x8A: "TXA", 0xA8: "TAY", 0x98: "TYA", 0x18: "CLC", 0x38: "SEC", 0xD8: "CLD",
                 0xF8: "SED", 0x58: "CLI", 0x78: "SEI", 0xB8: "CLV", 0xE8: "INX", 0xC8: "INY", 0xCA: "DEX",
                 0x88: "DEY", 0x00: "BRK", 0x40: "RTI", 0x60: "RTS", 0x20: "JSR", 0x4C: "JMP", 0x6C: "JMP",
                 0x1A: "INC", 0x3A: "DEC", 0x64: "STZ", 0x9C: "STZ", 0x89: "BIT", 0x04: "TSB", 0x14: "TRB",
                 0xDA: "PHX", 0xFA: "PLX", 0x5A: "PHY", 0x7A: "PLY", 0xC9: "CMP", 0xE0: "CPX", 0xC0: "CPY",
                 0x29: "AND", 0x09: "ORA", 0x49: "EOR", 0x0A: "ASL", 0x4A: "LSR", 0x2A: "ROL", 0x6A: "ROR"}
        t = Optable()
        for opc, mn in known.items():
            self.assertEqual(t.get(opc).mnemonic, mn, "opcode $%02X" % opc)
            self.assertEqual(REF_OPS[opc][0], mn, "opcode $%02X" % opc)


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
            decode_block(bytes([0xDB]), 0x0300)    # STP (WDC): fora do conjunto do Lynx
        self.assertIn("$DB", str(cm.exception))
        self.assertIn("$0300", str(cm.exception))

    def test_89_is_bit_immediate_not_sta_immediate(self):
        self.assertEqual(decode_block(bytes([0x89, 0x0F]), 0)[0].text(), "BIT #$0F")   # 65C02

    def test_brk_is_two_bytes(self):
        insns = decode_block(bytes([0x00, 0xFF, 0x60]), 0x100)
        self.assertEqual([(i.text(), i.length) for i in insns], [("BRK", 2), ("RTS", 1)])

    def test_wdc_extras_not_in_lynx_set_are_rejected(self):
        for opc in (0xCB, 0xDB, 0x0F, 0x07, 0x87):     # WAI, STP, BBR0, RMB0, SMB0
            with self.assertRaises(UnsupportedOpcode):
                decode_block(bytes([opc, 0, 0]), 0)

    def test_truncated(self):
        with self.assertRaises(TruncatedInstruction):
            decode_block(bytes([0xAD, 0x34]), 0)


if __name__ == "__main__":
    unittest.main()
