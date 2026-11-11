"""Relatório de elegibilidade e medição ARM."""
import os
import unittest

from lynx2c import ABI_VERSION, armsize
from lynx2c.ingest import build_bs93, ingest
from lynx2c.pipeline import analyze
from lynx2c.report import build_report

INC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "runtime", "include")


def program():
    code = bytes.fromhex("A200 CA D0FD 8D91FC AD00FD 6C0010")      # LDX #0; DEX; BNE *-1; STA $FC91; LDA $FD00; JMP ($1000)
    i = ingest(build_bs93(code, 0x0300))
    cfg, ops = analyze(i.data, i.load_addr, [i.entry])
    return i, cfg, ops


class TestReport(unittest.TestCase):
    def test_sections_and_counts(self):
        i, cfg, ops = program()
        r = build_report("t", cfg, ops, len(i.data), include_dir=INC, measure=False)
        for h in ("## Código alcançável", "## Flags e memória", "## Orçamento de código ARM", "## Avisos", "NÃO diz"):
            self.assertIn(h, r)
        self.assertIn("Suzy $FC00-FCFF 1", r)
        self.assertIn("Mikey $FD00-FDFF 1", r)
        self.assertIn("Saídas dinâmicas (RTS, RTI, JMP indireto, BRK) | 1", r)
        self.assertIn("ESTIMATIVA", r)                                   # sem medição, é rotulado como estimativa

    def test_warnings_listed(self):
        i, cfg, ops = program()
        r = build_report("t", cfg, ops, len(i.data), measure=False, smc_operands=[0x0301], hooks=[0x0400], notes=["x"])
        self.assertIn("$0301", r)
        self.assertIn("$0400", r)

    @unittest.skipUnless(armsize.available(), "clang/llvm-size ausentes")
    def test_measured_arm_numbers_present_and_consistent(self):
        i, cfg, ops = program()
        r = build_report("t", cfg, ops, len(i.data), include_dir=INC, measure=True)
        self.assertIn("Medido com clang", r)
        self.assertIn("Expansão", r)
        self.assertNotIn("ESTIMATIVA", r)

    @unittest.skipUnless(armsize.available(), "clang/llvm-size ausentes")
    def test_measure_is_big_endian_arm_and_scales_with_code(self):
        import tempfile
        from lynx2c.emit_c import _HEADER, emit_overlay
        sizes = []
        for n in (4, 40):
            img = b"".join(bytes([0x85, 0x10 + k]) for k in range(n)) + b"\x60"     # STA zp distintos: o clang não funde
            cfg, ops = analyze(img, 0x300, [0x300])
            with tempfile.TemporaryDirectory() as td:
                p = os.path.join(td, "g.c")
                open(p, "w").write(_HEADER % {"ver": "t", "abi": ABI_VERSION} + "\n" + emit_overlay(0, cfg, ops))
                sizes.append(armsize.measure_c(p, INC)["text"])
        self.assertGreater(sizes[1], sizes[0])
        self.assertEqual(sizes[0] % 4, 0)                               # modo ARM: instruções de 4 bytes


if __name__ == "__main__":
    unittest.main()
