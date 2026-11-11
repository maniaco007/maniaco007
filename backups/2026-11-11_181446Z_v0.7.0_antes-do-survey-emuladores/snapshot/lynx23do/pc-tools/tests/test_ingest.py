"""Estágio A: .lnx, BS93 e imagem plana (formatos confirmados contra o Handy)."""
import unittest

from lynx2c.ingest import IngestError, build_bs93, build_lnx, ingest


class TestLnx(unittest.TestCase):
    def test_roundtrip_fields(self):
        raw = build_lnx(bytes(128 * 1024), name="JOGO", manufacturer="ACME", rotation=2, audin=1, eeprom=3)
        i = ingest(raw)
        self.assertEqual((i.kind, i.name, i.manufacturer, i.rotation, i.audin, i.eeprom),
                         ("lnx", "JOGO", "ACME", "direita", True, 3))
        self.assertEqual((i.bank0_bytes, i.bank1_bytes, len(i.data)), (128 * 1024, 0, 128 * 1024))
        self.assertEqual(i.warnings, [])
        self.assertFalse(i.executable_known)               # boot cifrado: código não é conhecido

    def test_bank_sizes_follow_page_size_times_256(self):
        for kb, page in ((64, 0x100), (128, 0x200), (256, 0x400), (512, 0x800)):
            raw = build_lnx(bytes(kb * 1024))
            self.assertEqual(raw[4] | raw[5] << 8, page)   # campo little-endian no arquivo
            self.assertEqual(ingest(raw).bank0_bytes, kb * 1024)

    def test_two_banks(self):
        i = ingest(build_lnx(bytes(256 * 1024), bytes(64 * 1024)))
        self.assertEqual((i.bank0_bytes, i.bank1_bytes), (256 * 1024, 64 * 1024))

    def test_size_mismatch_is_a_warning_not_an_error(self):
        raw = build_lnx(bytes(128 * 1024))[:-100]
        self.assertTrue(any("bancos declarados" in w for w in ingest(raw).warnings))

    def test_invalid_page_size_is_an_error(self):
        raw = bytearray(build_lnx(bytes(64 * 1024)))
        raw[4], raw[5] = 0x34, 0x12
        with self.assertRaises(IngestError):
            ingest(bytes(raw))

    def test_invalid_rotation_falls_back_like_handy(self):
        raw = bytearray(build_lnx(bytes(64 * 1024)))
        raw[58] = 9
        i = ingest(bytes(raw))
        self.assertEqual(i.rotation, "nenhuma")
        self.assertTrue(i.warnings)


class TestBs93(unittest.TestCase):
    def test_header_is_executable_bra_and_fields_are_big_endian(self):
        code = bytes([0xA9, 0x01, 0x60])
        raw = build_bs93(code, 0x0200)
        self.assertEqual(raw[:2], b"\x80\x08")                         # BRA +8 pula o resto do cabeçalho
        self.assertEqual((raw[2], raw[3]), (0x02, 0x00))               # load_address BIG-endian
        self.assertEqual(raw[6:10], b"BS93")
        i = ingest(raw)
        self.assertEqual((i.kind, i.load_addr, i.entry, i.executable_known), ("bs93", 0x0200 - 10, 0x0200 - 10, True))
        self.assertEqual(i.data, raw)
        self.assertEqual(i.warnings, [])

    def test_bra_in_header_lands_on_first_code_byte(self):
        from lynx2c.pipeline import analyze
        raw = build_bs93(bytes([0xA9, 0x01, 0x60]), 0x0300)
        i = ingest(raw)
        cfg, _ = analyze(i.data, i.load_addr, [i.entry])
        self.assertEqual(cfg.starts, [0x02F6, 0x0300])                 # cabeçalho (BRA) e código a partir de load_address
        self.assertEqual(cfg.blocks[0x02F6].succs, [0x0300])

    def test_oversize_and_undersize_header(self):
        raw = bytearray(build_bs93(bytes(20), 0x0200))
        raw[4], raw[5] = 0x00, 0xFF
        self.assertTrue(any("maior" in w for w in ingest(bytes(raw)).warnings))
        raw[4], raw[5] = 0x00, 0x0C
        i = ingest(bytes(raw))
        self.assertTrue(any("menor" in w for w in i.warnings))
        self.assertEqual(len(i.data), 12)

    def test_bad_first_bytes_rejected(self):
        raw = bytearray(build_bs93(b"\x60", 0x0200))
        raw[0] = 0x00
        with self.assertRaises(IngestError):
            ingest(bytes(raw))


class TestRaw(unittest.TestCase):
    def test_raw_needs_org(self):
        with self.assertRaises(IngestError):
            ingest(bytes([0x60]))
        i = ingest(bytes([0x60]), org=0x0400)
        self.assertEqual((i.kind, i.load_addr, i.entry), ("raw", 0x0400, 0x0400))

    def test_sha256_is_stable(self):
        self.assertEqual(ingest(b"\x60", org=0).sha256, ingest(b"\x60", org=0x10).sha256)


if __name__ == "__main__":
    unittest.main()
