"""Modelos de CPU (docs/12 §2): core (178) / lynx1 / lynx2 — NOPs indocumentados, CB/DB, Rockwell, LNX2, CLI.

A tabela do tradutor (optable.json, gerada por gen_optable.py) é comparada com a do ORÁCULO (core65c02.ref_table),
que a DERIVA por regra (nibble baixo, bit n = opcode>>4) — duas fontes escritas separadamente. As fontes EXTERNAS
(Handy e Gearlynx) cobrem os ciclos: ver test_handy_reference.py e tools/crosscheck_gearlynx.py.
"""
import contextlib
import io
import json
import os
import unittest

from lynx2c import cli
from lynx2c.asm import assemble
from lynx2c.cfg import build_cfg
from lynx2c.decode import UnsupportedOpcode, decode_block, decode_one
from lynx2c.emit_c import emit_overlay
from lynx2c.ingest import IngestError, build_lnx, build_lnx2, ingest, lnx2_bank_size
from lynx2c.optable import Optable
from lynx2c.pipeline import analyze
from lynxtrace.core65c02 import REF_OPS, _LEN, base_cycles, ext_cycles, ref_table

HERE = os.path.dirname(os.path.abspath(__file__))
HANDY = os.path.join(HERE, "..", "lynx2c", "data", "handy_reference.json")


def H(s):
    return bytes.fromhex(s.replace(" ", ""))


class TestTables(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(len(Optable("core").by_opcode), 178)
        self.assertEqual(len(Optable("lynx1").by_opcode), 256)      # nenhum opcode indefinido
        self.assertEqual(len(Optable("lynx2").by_opcode), 256)

    def test_unknown_model(self):
        with self.assertRaises(ValueError):
            Optable("lynx3")

    def test_matches_oracle_for_every_opcode(self):
        for model in ("lynx1", "lynx2"):
            t, ref = Optable(model), ref_table(model)
            self.assertEqual(set(t.by_opcode), set(ref))
            for opc, (mn, mode) in ref.items():
                i = t.get(opc)
                ec = ext_cycles(opc, mn, mode)
                want = base_cycles(mn, mode) if ec is None else ec
                self.assertEqual((i.mnemonic, i.mode, i.length, i.cycles), (mn, mode, _LEN[mode], want),
                                 "%s $%02X" % (model, opc))

    def test_core_is_a_subset_with_identical_entries(self):
        core = Optable("core").by_opcode
        for model in ("lynx1", "lynx2"):
            full = Optable(model).by_opcode
            for opc, i in core.items():
                self.assertEqual(full[opc], i)

    def test_one_byte_nops_cb_db_and_lynx_i_vs_ii_difference(self):
        l1, l2 = Optable("lynx1"), Optable("lynx2")
        for opc in (0xCB, 0xDB, 0x03, 0x0B, 0xFB):                  # WAI/STP do WDC e demais x3/xB
            for t in (l1, l2):
                self.assertEqual((t.get(opc).mnemonic, t.get(opc).length, t.get(opc).cycles), ("NOP", 1, 1))
        self.assertEqual((l1.get(0x07).mnemonic, l1.get(0x07).length), ("NOP", 1))     # Lynx I: x7/xF são NOP
        self.assertEqual((l1.get(0x8F).mnemonic, l1.get(0x8F).length), ("NOP", 1))
        self.assertEqual((l2.get(0x07).mnemonic, l2.get(0x87).mnemonic), ("RMB0", "SMB0"))
        self.assertEqual((l2.get(0x0F).mnemonic, l2.get(0x8F).mnemonic, l2.get(0x7F).mnemonic), ("BBR0", "BBS0", "BBR7"))
        self.assertEqual(l2.get(0xFF).mnemonic, "BBS7")
        self.assertEqual(l2.get(0xF7).mnemonic, "SMB7")

    def test_multibyte_nops_have_documented_size_and_cycles(self):
        want = {0x02: (2, 2), 0x22: (2, 2), 0x42: (2, 2), 0x62: (2, 2), 0x82: (2, 2), 0xC2: (2, 2), 0xE2: (2, 2),
                0x44: (2, 3), 0x54: (2, 4), 0xD4: (2, 4), 0xF4: (2, 4), 0x5C: (3, 8), 0xDC: (3, 4), 0xFC: (3, 4)}
        for model in ("lynx1", "lynx2"):
            for opc, (n, c) in want.items():
                i = Optable(model).get(opc)
                self.assertEqual((i.mnemonic, i.length, i.cycles, i.undoc), ("NOP", n, c, True), "$%02X" % opc)

    def test_handy_agrees_on_multibyte_nop_and_bit_branch_cycles(self):
        """Terceira fonte (Handy): para os NOPs de 2/3 bytes e BBRn/BBSn o ciclo-base (n+1) coincide.
        (Os de 1 byte e RMB/SMB o Handy trata como ILLEGAL com custos próprios: sem valor de comparação.)"""
        with open(HANDY, encoding="utf-8") as f:
            h = json.load(f)["opcodes"]
        t = Optable("lynx2")
        # Anomalia do Handy (fixada): o slot $BF (BBS3) tem n=3 (4 ciclos) enquanto os outros 15 têm n=4 (5 ciclos);
        # Gearlynx e a regra do Rockwell dão 5 para todos. Qualquer outra divergência faz o teste falhar.
        handy_anomaly = {0xBF: 4}
        for opc in (0x02, 0x22, 0x42, 0x62, 0x82, 0xC2, 0xE2, 0x44, 0x54, 0xD4, 0xF4, 0x5C, 0xDC, 0xFC) + \
                tuple(0x0F | b << 4 for b in range(8)) + tuple(0x8F | b << 4 for b in range(8)):
            self.assertEqual(h["%02X" % opc]["n"] + 1, handy_anomaly.get(opc, t.get(opc).cycles), "$%02X" % opc)
            if opc not in handy_anomaly:
                self.assertEqual(t.get(opc).cycles, h["%02X" % opc]["n"] + 1)

    def test_undocumented_flag(self):
        l2 = Optable("lynx2")
        self.assertTrue(l2.get(0x03).undoc)
        self.assertFalse(l2.get(0x07).undoc)            # Rockwell é documentado
        self.assertFalse(l2.get(0xEA).undoc)


class TestDecodeExtensions(unittest.TestCase):
    def test_bbr_target_forward_and_backward(self):
        fwd = decode_one(H("0F 10 05"), 0, 0x0300, Optable("lynx2"))
        self.assertEqual((fwd.mnemonic, fwd.length, fwd.operand & 0xFF, fwd.target), ("BBR0", 3, 0x10, 0x0308))
        back = decode_one(H("8F 20 FB"), 0, 0x0300, Optable("lynx2"))        # BBS0 $20, -5 => 0x0303-5
        self.assertEqual((back.mnemonic, back.target, back.next_addr), ("BBS0", 0x02FE, 0x0303))
        self.assertEqual(fwd.text(), "BBR0 $10,$0308")

    def test_rmb_smb_text_and_operand(self):
        i = decode_one(H("B7 44"), 0, 0, Optable("lynx2"))
        self.assertEqual((i.mnemonic, i.text(), i.length, i.operand), ("SMB3", "SMB3 $44", 2, 0x44))
        self.assertEqual(decode_one(H("37 44"), 0, 0, Optable("lynx2")).mnemonic, "RMB3")

    def test_nop_operands_are_consumed_not_executed(self):
        insns = decode_block(H("5C 34 12 EA 44 99 60"), 0x200, Optable("lynx1"))
        self.assertEqual([(i.mnemonic, i.length, i.addr) for i in insns],
                         [("NOP", 3, 0x200), ("NOP", 1, 0x203), ("NOP", 2, 0x204), ("RTS", 1, 0x206)])

    def test_truncated_multibyte_nop(self):
        from lynx2c.decode import TruncatedInstruction
        with self.assertRaises(TruncatedInstruction):
            decode_block(H("5C 34"), 0, Optable("lynx1"))

    def test_lynx1_rejects_nothing_but_core_rejects_extensions(self):
        for opc in range(256):
            decode_one(bytes([opc, 0, 0]), 0, 0x400, Optable("lynx1"))     # nenhum levanta
        with self.assertRaises(UnsupportedOpcode):
            decode_one(H("0F 00 00"), 0, 0, Optable("core"))


class TestCfgAndEmit(unittest.TestCase):
    def test_bit_branch_is_a_branch_block_with_two_successors(self):
        # BBR0 $10,+2 ; SMB0 $10 ; RTS   (alvo: RTS)
        cfg, ops = analyze(H("0F 10 02 87 10 60"), 0x300, [0x300], cpu="lynx2")
        b = cfg.blocks[0x300]
        self.assertEqual((b.kind, b.succs), ("branch", [0x0305, 0x0303]))
        self.assertEqual(cfg.model, "lynx2")
        self.assertEqual(cfg.undoc, [])

    def test_undoc_nops_are_listed_and_ignored_data_is_not(self):
        cfg, _ = analyze(H("03 EA 44 00 60 FF FF"), 0x300, [0x300], cpu="lynx1")   # $FF após RTS: dado, nunca decodificado
        self.assertEqual(cfg.undoc, [0x300, 0x302])

    def test_same_bytes_are_nop_in_lynx1_and_rockwell_in_lynx2(self):
        code = H("07 EA 60")                               # x7: NOP de 1 byte (Lynx I) | RMB0 $EA (Lynx II)
        c1, _ = analyze(code, 0x300, [0x300], cpu="lynx1")
        c2, _ = analyze(code, 0x300, [0x300], cpu="lynx2")
        self.assertEqual([i.mnemonic for i in c1.blocks[0x300].insns], ["NOP", "NOP", "RTS"])
        self.assertEqual([i.mnemonic for i in c2.blocks[0x300].insns], ["RMB0", "RTS"])

    def test_generated_c_for_rockwell(self):
        cfg, ops = analyze(H("0F 10 02 87 10 17 11 60"), 0x300, [0x300], cpu="lynx2")
        for phase in (1, 2):
            c = emit_overlay(0, cfg, ops, phase=phase)
            self.assertIn("lx_ram[0x10] = (lx_u8)(lx_ram[0x10] | 0x01);", c)      # SMB0 $10
            self.assertIn("lx_ram[0x11] = (lx_u8)(lx_ram[0x11] & 0xFD);", c)      # RMB1 $11 (bit 1)
            self.assertIn("!(m & 0x01)", c)                                        # BBR0
            self.assertIn("lx_ram[0x10]", c)

    def test_nop_emits_no_memory_access(self):
        cfg, ops = analyze(H("5C 00 FC EA 60"), 0x300, [0x300], cpu="lynx1")     # NOP $FC00 (abs, não lido!) ; NOP ; RTS
        c = emit_overlay(0, cfg, ops, phase=2)
        self.assertNotIn("lx_suzy_read", c)
        self.assertNotIn("lx_io_read", c)

    def test_bit_branch_taken_cycle_extra_matches_page_cross(self):
        cfg, ops = analyze(H("0F 10 F0") + b"\xEA" * 3, 0x400, [0x400], cpu="lynx2")   # próximo=$0403, alvo=$0403-16=$03F3
        self.assertEqual(cfg.blocks[0x400].succs[0], 0x3F3)
        c = emit_overlay(0, cfg, ops, phase=1)
        self.assertIn("cpu->cycles += 2;", c)                                   # +1 tomado +1 cruzando página
        cfg, ops = analyze(H("0F 10 02") + b"\xEA" * 3, 0x400, [0x400], cpu="lynx2")   # mesma página: só +1
        self.assertIn("cpu->cycles += 1;", emit_overlay(0, cfg, ops, phase=1))


class TestAsm(unittest.TestCase):
    def test_zprel_roundtrip(self):
        code, labels = assemble(0x300, [("BBS5", "zprel", 0x20, "fim"), ("RMB5", "zp", 0x20), ("L", "fim"), ("RTS", "imp")])
        i = decode_one(code, 0, 0x300, Optable("lynx2"))
        self.assertEqual((i.mnemonic, i.target), ("BBS5", labels["fim"]))
        self.assertEqual(code[0], 0x8F | 5 << 4)
        self.assertEqual(code[3], 0x07 | 5 << 4)

    def test_out_of_range(self):
        with self.assertRaises(ValueError):
            assemble(0, [("BBR0", "zprel", 0, 0x400)])


class TestLnx2(unittest.TestCase):
    ROM = bytes(range(256)) * 256         # 64 KB

    def test_bank_size_formula(self):
        self.assertEqual(lnx2_bank_size(0), 0)
        self.assertEqual(lnx2_bank_size(3 << 6 | 0 << 3 | 0), 16 * 2)
        self.assertEqual(lnx2_bank_size(3 << 6 | 7 << 3 | 7), (16 << 7) * (2 << 7))     # 2 KB x 256 = 512 KB

    def test_roundtrip_lynx_i(self):
        raw = build_lnx2([(3, self.ROM)], name="JOGO", eeprom=3)
        info = ingest(raw)
        self.assertEqual((info.kind, info.cpu, info.name, info.eeprom), ("lnx", "lynx1", "JOGO", 3))
        self.assertEqual((info.bank0_bytes, info.bank1_bytes, len(info.data)), (65536, 0, 65536))
        self.assertEqual(info.warnings, [])
        self.assertFalse(info.audin)

    def test_lynx_ii_flag_and_audin_banks(self):
        raw = build_lnx2([(3, self.ROM), (3, self.ROM[:32768]), (3, self.ROM)], flags=1)
        info = ingest(raw)
        self.assertEqual(info.cpu, "lynx2")
        self.assertTrue(info.audin)                                # banco 0A presente
        self.assertEqual([t for t, _ in info.lnx2_banks], [3, 3, 3, 0])
        self.assertEqual(info.bank1_bytes, 65536)

    def test_ram_bank_warns_and_unknown_flags_warn(self):
        raw = build_lnx2([(3, self.ROM), (0, b""), (1, bytes(512))], flags=0x03)
        info = ingest(raw)
        self.assertTrue(any("RAM persistente" in w for w in info.warnings))
        self.assertTrue(any("flags LNX2" in w for w in info.warnings))

    def test_size_mismatch_warns(self):
        raw = build_lnx2([(3, self.ROM)]) + b"\0" * 7
        self.assertTrue(any("bancos declarados" in w for w in ingest(raw).warnings))

    def test_lnx_v1_unchanged(self):
        info = ingest(build_lnx(self.ROM))
        self.assertEqual((info.kind, info.cpu), ("lnx", "lynx1"))


class TestCli(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_default_is_lynx1_and_warns_about_undoc(self):
        rc, out, err = self.run_cli(["cfg", "--org", "0x300", "--hex", "03 EA 60"])
        self.assertEqual(rc, 0)
        self.assertIn("indocumentado", err)

    def test_core_is_strict(self):
        rc, out, err = self.run_cli(["cfg", "--org", "0x300", "--cpu", "core", "--hex", "03 EA 60"])
        self.assertEqual(rc, 2)
        self.assertIn("$03", err)

    def test_lynx2_disasm(self):
        rc, out, err = self.run_cli(["disasm", "--org", "0x300", "--cpu", "lynx2", "--hex", "0F 10 02 87 10"])
        self.assertEqual(rc, 0)
        self.assertIn("BBR0", out)
        self.assertIn("SMB0", out)

    def test_same_bytes_in_lynx1_disasm_are_nops(self):
        rc, out, err = self.run_cli(["disasm", "--org", "0x300", "--cpu", "lynx1", "--hex", "87 EA"])
        self.assertEqual(rc, 0)
        self.assertIn("NOP[87]", out)


if __name__ == "__main__":
    unittest.main()
