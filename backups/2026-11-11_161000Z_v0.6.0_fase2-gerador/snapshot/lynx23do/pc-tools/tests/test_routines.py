"""Fase 2: particionamento em rotinas e estrutura do código gerado."""
import re
import unittest

from lynx2c.emit_c import emit_overlay
from lynx2c.pipeline import analyze
from lynx2c.routines import DEFAULT_MAX_BLOCKS, partition, roots_of


def H(s):
    return bytes.fromhex(s.replace(" ", ""))


# LDX #3; L: JSR f; DEX; BNE L; RTS ; f: INC $10; RTS      (f em $0209)
LOOP_JSR = H("A203 200902 CA D0FA 60 EE1000 60")
# laço simples com blocos encadeados por desvios, sem chamadas
CHAIN = H("A900 F004 A901 D002 A902 8510 60")


class TestPartition(unittest.TestCase):
    def check_invariants(self, cfg, part):
        owner = {}
        for r, blks in part.items():
            self.assertIn(r, blks)
            for b in blks:
                self.assertNotIn(b, owner, "bloco $%04X em duas rotinas" % b)    # cada bloco pertence a UMA rotina
                owner[b] = r
        self.assertEqual(set(owner), set(cfg.blocks))                           # e todo bloco pertence a alguma

    def test_every_block_in_exactly_one_routine(self):
        for img in (LOOP_JSR, CHAIN):
            cfg, _ = analyze(img, 0x200, [0x200])
            for mb in (0, 1, 2, 3, DEFAULT_MAX_BLOCKS):
                self.check_invariants(cfg, partition(cfg, mb))

    def test_call_targets_and_continuations_are_roots(self):
        cfg, _ = analyze(LOOP_JSR, 0x200, [0x200])
        roots = roots_of(cfg, 0)
        self.assertIn(0x0209, roots)                                            # alvo do JSR
        self.assertIn(0x0205, roots)                                            # continuação do JSR
        self.assertIn(0x0200, roots)                                            # entrada

    def test_block_reached_from_two_roots_becomes_root(self):
        cfg, _ = analyze(LOOP_JSR, 0x200, [0x200])
        self.assertIn(0x0202, roots_of(cfg, 0))                                 # 0x0200 cai nele e 0x0205 volta a ele

    def test_max_blocks_splits_big_routines(self):
        cfg, _ = analyze(CHAIN, 0x200, [0x200])
        unbounded = partition(cfg, 0)
        split = partition(cfg, 2)
        self.assertLess(len(unbounded), len(split))
        self.assertTrue(all(len(b) <= 2 for b in split.values()))

    def test_entries_are_always_roots(self):
        cfg, _ = analyze(CHAIN, 0x200, [0x200, 0x204])
        self.assertTrue({0x200, 0x204} <= roots_of(cfg, 0))

    def test_deterministic(self):
        cfg, _ = analyze(LOOP_JSR, 0x200, [0x200])
        self.assertEqual(partition(cfg, 3), partition(cfg, 3))


class TestPhase2Code(unittest.TestCase):
    def gen(self, img, entries=(0x200,), mb=0):
        cfg, ops = analyze(img, 0x200, list(entries))
        return cfg, emit_overlay(0, cfg, ops, phase=2, max_blocks=mb)

    def test_registers_are_locals_in_the_body(self):
        cfg, c = self.gen(CHAIN)
        body = c.split("L_exit:")[0]
        loads = re.findall(r"^    \w+ = cpu->\w+;$", body, re.M)
        rest = [l for l in body.splitlines() if "cpu->" in l and l not in loads]
        self.assertEqual(rest, [], "acesso a LxCpu fora de carga/gravação: %s" % rest[:3])

    def test_single_exit_label_and_exit_checks_event(self):
        _, c = self.gen(LOOP_JSR)
        for fn in re.findall(r"^lx_u32 lx_ov0_[0-9A-F]{4}\(.*?^}\n", c, re.S | re.M):
            self.assertEqual(fn.count("L_exit:"), 1)
            self.assertIn("return lx_sched_service(cpu, pc);", fn)

    def test_entry_switch_lists_every_block_of_a_multiblock_routine(self):
        cfg, c = self.gen(CHAIN)
        part = partition(cfg, 0)
        root, blks = max(part.items(), key=lambda kv: len(kv[1]))
        fn = re.search(r"^lx_u32 lx_ov0_%04X\(.*?^}\n" % root, c, re.S | re.M).group(0)
        self.assertEqual(len(re.findall(r"case \d+: goto L_", fn)), len(blks))

    def test_dispatch_table_lists_all_leaders_with_sub_entries(self):
        cfg, c = self.gen(CHAIN)
        rows = re.findall(r"\{ 0x([0-9A-F]{4}), 0x([0-9A-F]{4}) \| (?:0|LX_DE_RETADDR), (lx_ov0_[0-9A-F]{4}) \}", c)
        self.assertEqual(sorted(int(a, 16) for a, _, _ in rows), cfg.starts)
        subs = {int(a, 16): int(s, 16) >> 4 for a, s, _ in rows}
        self.assertEqual(subs[min(partition(cfg, 0))], 0)                      # a raiz é a sub-entrada 0

    def test_no_unused_labels_in_single_block_routine(self):
        _, c = self.gen(H("A901 8510 60"))
        self.assertNotIn("L_0200:", c)                                         # único bloco sem laço: sem rótulo

    def test_self_loop_gets_a_label(self):
        _, c = self.gen(H("A901 D0FE"))                                        # LDA #1; BNE * (laço no próprio bloco)
        self.assertIn("L_0200:", c)

    def test_c89_clean(self):
        _, c = self.gen(LOOP_JSR)
        self.assertNotIn("//", c)


if __name__ == "__main__":
    unittest.main()
