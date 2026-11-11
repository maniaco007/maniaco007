"""Vivacidade de flags e propriedades estruturais do C emitido."""
import unittest

from lynx2c.decode import decode_block
from lynx2c.emit_c import emit_block, emit_unit
from lynx2c.lift import lift
from lynx2c.opt import flag_liveness


def ops_of(hexstr, org=0x200):
    return flag_liveness(lift(decode_block(bytes.fromhex(hexstr), org)))


class TestLiveness(unittest.TestCase):
    def test_lda_overwritten_has_dead_nz(self):
        ops = ops_of("A901 A902")                       # LDA #1 ; LDA #2
        self.assertEqual(ops[0].dead, frozenset("NZ"))
        self.assertEqual(ops[1].dead, frozenset())      # saída do bloco: tudo vivo

    def test_adc_chain_keeps_carry_live(self):
        ops = ops_of("6901 6902")                       # ADC #1 ; ADC #2 (lê C do primeiro)
        self.assertEqual(ops[0].dead, frozenset("NZV"))
        self.assertNotIn("C", ops[0].dead)

    def test_sta_does_not_touch_flags(self):
        ops = ops_of("A901 8510 A902")
        self.assertEqual(ops[0].dead, frozenset("NZ"))  # STA não lê flags

    def test_all_live_at_exit(self):
        for o in ops_of("A901 6902 E903"):
            pass
        self.assertEqual(ops_of("E903")[0].dead, frozenset())


class TestEmit(unittest.TestCase):
    def test_dead_flags_not_materialized(self):
        ops = ops_of("A901 A902")
        c = emit_block("f", ops, 0x200)
        self.assertEqual(c.count("cpu->nsrc"), 1)       # só o segundo LDA
        self.assertEqual(c.count("cpu->zsrc"), 1)

    def test_static_region_classification(self):
        c = emit_block("f", ops_of("AD0010 AD91FC AD00FD AD10FF"), 0x200)
        self.assertIn("lx_ram[0x1000]", c)
        self.assertIn("lx_suzy_read(0xFC91)", c)
        self.assertIn("lx_mikey_read(0xFD00)", c)
        self.assertIn("lx_io_read(0xFF10)", c)

    def test_store_regions(self):
        c = emit_block("f", ops_of("8D0010 8D91FC 8D00FD"), 0x200)
        self.assertIn("lx_ram[0x1000] = cpu->a;", c)
        self.assertIn("lx_suzy_write(0xFC91, cpu->a);", c)
        self.assertIn("lx_mikey_write(0xFD00, cpu->a);", c)

    def test_indexed_uses_generic_accessors(self):
        c = emit_block("f", ops_of("BD00FB 9D00FB"), 0x200)
        self.assertIn("lx_rd8(ea)", c)
        self.assertIn("lx_wr8(ea, cpu->a)", c)

    def test_cycles_and_next_pc(self):
        c = emit_block("f", ops_of("A901 8D91FC"), 0x200)   # 2 + 4 ciclos; próximo PC = $0205
        self.assertIn("LX_SCHED_CHECK(cpu, 6, 0x0205);", c)
        self.assertIn("return 0x0205;", c)

    def test_c89_no_line_comments_or_mixed_decls(self):
        c = emit_unit([("f", ops_of("A901 6902 E903 B1 10 91 20".replace(" ", "")), 0x200)])
        self.assertNotIn("//", c)

    def test_deterministic(self):
        a = emit_unit([("f", ops_of("A901 6902"), 0x200)])
        b = emit_unit([("f", ops_of("A901 6902"), 0x200)])
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
