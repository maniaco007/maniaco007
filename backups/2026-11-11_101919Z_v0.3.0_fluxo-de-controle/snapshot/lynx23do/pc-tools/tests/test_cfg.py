"""CFG, líderes, erros explícitos e vivacidade de flags ENTRE blocos."""
import unittest

from lynx2c.cfg import OverlapError, build_cfg
from lynx2c.decode import UnsupportedOpcode, TruncatedInstruction
from lynx2c.emit_c import emit_overlay
from lynx2c.pipeline import analyze
from independent import independent_leaders


def H(s):
    return bytes.fromhex(s.replace(" ", ""))


PROG = H("A901 200B02 F002 6902 60 EA 60")   # LDA #1; JSR $020B; BEQ +2; ADC #2; RTS; NOP(dado); RTS


class TestCfg(unittest.TestCase):
    def test_blocks_and_successors(self):
        cfg = build_cfg(PROG, 0x200, [0x200])
        self.assertEqual(cfg.starts, [0x200, 0x205, 0x207, 0x209, 0x20B])
        self.assertEqual(cfg.blocks[0x200].kind, "call")
        self.assertEqual(cfg.blocks[0x200].succs, [0x20B, 0x205])
        self.assertTrue(cfg.blocks[0x205].retaddr)               # continuação do JSR
        self.assertEqual(cfg.blocks[0x205].succs, [0x209, 0x207])
        self.assertEqual(cfg.blocks[0x207].kind, "fall")

    def test_leaders_match_independent_algorithm(self):
        cfg = build_cfg(PROG, 0x200, [0x200])
        self.assertEqual(set(cfg.starts), independent_leaders(PROG, 0x200, [0x200]))

    def test_unreachable_bytes_are_data_not_decoded(self):
        cfg = build_cfg(PROG, 0x200, [0x200])                    # $EA em $020A nunca é decodificado
        covered = {i.addr for b in cfg.blocks.values() for i in b.insns}
        self.assertNotIn(0x20A, covered)

    def test_reachable_unsupported_opcode_is_explicit_error(self):
        with self.assertRaises(UnsupportedOpcode) as cm:
            build_cfg(H("A901 EA"), 0x300, [0x300])
        self.assertIn("$0302", str(cm.exception))

    def test_truncated_at_end_of_image(self):
        with self.assertRaises(TruncatedInstruction):
            build_cfg(H("A901 4C00"), 0x300, [0x300])

    def test_overlap_is_explicit_error(self):
        # BNE aponta para o meio de 'LDA $0100' ($0301 = operando) -> sobreposição
        with self.assertRaises(OverlapError):
            build_cfg(H("D0 01 AD 00 01 60"), 0x300, [0x300])

    def test_external_target_is_accepted(self):
        cfg = build_cfg(H("4C0090"), 0x300, [0x300])               # JMP $9000 fora da imagem
        self.assertEqual(cfg.blocks[0x300].succs, [0x9000])

    def test_extra_entry_seed(self):
        cfg = build_cfg(H("6C0010 A901 60"), 0x300, [0x300, 0x303])
        self.assertIn(0x303, cfg.blocks)
        self.assertEqual(cfg.blocks[0x300].kind, "jump_ind")

    def test_entry_outside_image_rejected(self):
        with self.assertRaises(ValueError):
            build_cfg(H("60"), 0x300, [0x400])

    def test_deterministic_order(self):
        a = build_cfg(PROG, 0x200, [0x200])
        b = build_cfg(PROG, 0x200, [0x200])
        self.assertEqual([(s, a.blocks[s].succs) for s in a.starts], [(s, b.blocks[s].succs) for s in b.starts])


class TestLivenessAcrossBlocks(unittest.TestCase):
    def test_n_dead_when_successors_redefine_it(self):
        # LDA #0; BEQ L; (fall) LDA #5 ; L: LDA #7 ; BRA self   -> N do 1º LDA morto, Z vivo (BEQ lê Z)
        img = H("A900 F002 A905 A907 80FE")
        cfg, ops = analyze(img, 0x200, [0x200])
        first = ops[0x200][0]
        self.assertEqual(first.dead, frozenset("N"))

    def test_far_use_needs_second_fixpoint_iteration(self):
        # $0200: LDA #0; BRA $0210 | $0210: BRA $0220 | $0220: BEQ $0222 | $0222: BRA * (nada vivo depois)
        # O uso de Z está a DOIS saltos de distância, em blocos de endereço crescente: a análise varre
        # em ordem de endereço, então só as iterações seguintes do ponto fixo propagam Z até o LDA.
        img = H("A900 800C") + bytes([0xFF] * 12) + H("800E") + bytes([0xFF] * 14) + H("F000 80FE")
        cfg, ops = analyze(img, 0x200, [0x200])
        self.assertEqual(cfg.starts, [0x200, 0x210, 0x220, 0x222])
        self.assertEqual(cfg.live_in[0x220], frozenset("Z"))
        self.assertEqual(cfg.live_in[0x210], frozenset("Z"))
        self.assertEqual(cfg.live_in[0x200], frozenset())          # LDA define Z antes de ser lido
        self.assertEqual(ops[0x200][0].dead, frozenset("N"))        # Z vivo (BEQ lê), N morto

    def test_precise_exits_keeps_everything_live(self):
        img = H("A900 F002 A905 A907 80FE")
        _, ops = analyze(img, 0x200, [0x200], precise_exits=True)
        self.assertEqual(ops[0x200][0].dead, frozenset())               # nada eliminado entre blocos

    def test_ret_and_indirect_keep_everything_live(self):
        for img in (H("A900 60"), H("A900 6C0010")):
            _, ops = analyze(img, 0x200, [0x200])
            self.assertEqual(ops[0x200][0].dead, frozenset())

    def test_call_keeps_flags_live(self):
        _, ops = analyze(H("A900 200503 60"), 0x200, [0x200])     # LDA #0; JSR $0305(externo)
        self.assertEqual(ops[0x200][0].dead, frozenset())

    def test_loop_carry_stays_live(self):
        # L: LDA #1; ADC #1; BCC L  (C definido pelo ADC é lido por BCC)
        _, ops = analyze(H("A901 6901 90FA"), 0x200, [0x200])
        adc = ops[0x200][1]
        self.assertNotIn("C", adc.dead)

    def test_liveness_never_marks_a_used_flag_dead(self):
        # propriedade: qualquer flag lido por um op posterior no MESMO bloco nunca é morto antes dele
        _, ops = analyze(H("6901 F002 6902 90FA 60"), 0x200, [0x200])
        for blk in ops.values():
            for i, op in enumerate(blk):
                for later in blk[i + 1:]:
                    if op.defs & later.uses:
                        break
                    # sem redefinição entre eles, uso posterior implica "vivo"
                for j in range(i + 1, len(blk)):
                    if op.defs & blk[j].uses and not any(op.defs & blk[k].defs & blk[j].uses for k in range(i + 1, j)):
                        self.assertFalse(op.dead & blk[j].uses)


class TestEmitStructure(unittest.TestCase):
    def test_overlay_tables_sorted_and_complete(self):
        cfg, ops = analyze(PROG, 0x200, [0x200])
        c = emit_overlay(0, cfg, ops)
        addrs = [int(x, 16) for x in __import__("re").findall(r"\{ 0x([0-9A-F]{4}), (?:0|LX_DE_RETADDR), lx_ov0_", c)]
        self.assertEqual(addrs, sorted(cfg.blocks))
        self.assertIn("LX_DE_RETADDR", c)
        self.assertIn("const LxOverlay lx_ov0", c)
        self.assertNotIn("//", c)

    def test_branch_cycles_static_page_cross(self):
        # BNE em $12FE com alvo $1302 (próxima página): +2 ciclos; alvo na mesma página: +1
        img = bytes([0xEA] * 0)  # placeholder para clareza
        from lynx2c.decode import decode_one
        far = decode_one(H("D0 02"), 0, 0x12FE)       # nxt=$1300, alvo=$1302 -> mesma página que nxt
        near = decode_one(H("D0 FC"), 0, 0x12FE)      # nxt=$1300, alvo=$12FC -> página anterior
        from lynx2c.emit_c import _taken_extra
        self.assertEqual(_taken_extra(far), 1)
        self.assertEqual(_taken_extra(near), 2)


if __name__ == "__main__":
    unittest.main()
