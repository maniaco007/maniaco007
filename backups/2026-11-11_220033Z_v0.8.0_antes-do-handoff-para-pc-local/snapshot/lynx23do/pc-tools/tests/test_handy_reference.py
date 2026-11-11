"""Comparação com uma fonte INDEPENDENTE: o emulador Handy (dados derivados em data/handy_reference.json).

O que o Handy valida: o CONJUNTO de opcodes do CPU do Lynx e os ciclos BASE de cada opcode.
O que ele NÃO valida: penalidade de cruzamento de página, +1 do desvio tomado, +1 do decimal (ele não os modela).
Divergências conhecidas ficam FIXADAS aqui, com a explicação; qualquer outra faz o teste falhar.
"""
import json
import os
import unittest

from lynx2c.optable import Optable

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "lynx2c", "data", "handy_reference.json")

# opcodes que o Handy implementa e que NÃO estão (ainda) na nossa tabela
# WAI/STP exigem o agendador (dormir até IRQ / parar): ficam como "não suportado" explícito até lá.
HANDY_ONLY = {0xCB: "WAI", 0xDB: "STP"}

# ciclos base: (opcode) -> (nosso, handy, explicação)
KNOWN_CYCLE_DIVERGENCES = {
    0x09: (2, 3, "ORA #imm: o Handy dá 3, mas TODOS os outros imediatos (AND/EOR/ADC/SBC/CMP/LDx) dão 2 — anomalia do Handy"),
    0x1E: (6, 7, "ASL abs,X: nós 6 (+1 ao cruzar página, 65C02); Handy 7 fixo (estilo NMOS). [VERIFY] no CPU do Lynx"),
    0x3E: (6, 7, "ROL abs,X: idem"),
    0x5E: (6, 7, "LSR abs,X: idem"),
    0x7E: (6, 7, "ROR abs,X: idem"),
    0x80: (2, 3, "BRA: nós 2 + 1 de 'desvio tomado' (sempre) = 3; o Handy já embute o +1 na base — mesma soma"),
}
ACC_FORMS = {"ASLA": "ASL", "LSRA": "LSR", "ROLA": "ROL", "RORA": "ROR", "INCA": "INC", "DECA": "DEC"}


def load():
    with open(REF, "r", encoding="utf-8") as f:
        raw = json.load(f)["opcodes"]
    return {int(k, 16): v for k, v in raw.items()}


class TestAgainstHandy(unittest.TestCase):
    def setUp(self):
        self.h = load()
        self.t = Optable()

    def test_handy_table_is_complete(self):
        self.assertEqual(sorted(self.h), list(range(256)))

    def test_opcode_set_matches_the_lynx_cpu(self):
        handy_valid = {k for k, v in self.h.items() if v["op"] != "ILLEGAL"}
        ours = set(self.t.by_opcode)
        self.assertEqual(handy_valid - ours, set(HANDY_ONLY), "opcodes do Handy fora da nossa tabela")
        self.assertEqual(ours - handy_valid, set(), "opcodes nossos que o Handy trata como ilegais")
        for k, mn in HANDY_ONLY.items():
            self.assertEqual(self.h[k]["op"], mn)

    def test_rockwell_and_undefined_nops_are_illegal_in_handy_too(self):
        # BBRn/BBSn/RMBn/SMBn ($0F,$1F..$7F,$8F..$FF e $07,$17..$F7) e NOPs de 2/3 bytes
        for opc in list(range(0x07, 0x100, 0x10)) + list(range(0x0F, 0x100, 0x10)) + [0x02, 0x22, 0x42, 0x62, 0x82, 0xC2, 0xE2,
                                                                                  0x44, 0x54, 0xD4, 0xF4, 0x5C, 0xDC, 0xFC]:
            self.assertEqual(self.h[opc]["op"], "ILLEGAL", "$%02X" % opc)
            self.assertIsNone(self.t.get(opc), "$%02X" % opc)

    def test_mnemonics_match(self):
        for opc, info in self.t.by_opcode.items():
            name = ACC_FORMS.get(self.h[opc]["op"], self.h[opc]["op"])
            self.assertEqual(info.mnemonic, name, "opcode $%02X" % opc)

    def test_base_cycles_match_except_known_divergences(self):
        seen = {}
        for opc, info in self.t.by_opcode.items():
            hc = self.h[opc]["n"] + 1
            if info.cycles != hc:
                seen[opc] = (info.cycles, hc)
        self.assertEqual(set(seen), set(KNOWN_CYCLE_DIVERGENCES), "divergências novas ou resolvidas: %s" % seen)
        for opc, (ours, handy, _why) in KNOWN_CYCLE_DIVERGENCES.items():
            self.assertEqual(seen[opc], (ours, handy), "$%02X" % opc)

    def test_agreement_count(self):
        eq = sum(1 for opc, i in self.t.by_opcode.items() if i.cycles == self.h[opc]["n"] + 1)
        self.assertEqual((eq, len(self.t.by_opcode)), (172, 178))


if __name__ == "__main__":
    unittest.main()
