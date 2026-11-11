"""Ponta a ponta no PC: homebrew 65C02 -> lynx2c build -> C89 -> gcc -> runtime (Mikey/vídeo/agendador) -> PPM.

A imagem ESPERADA é calculada aqui, de forma independente, a partir do que o programa de demonstração promete
(paleta pen p = verde p / vermelho 15-p / azul p; 16 barras de 10 px; os 2 primeiros pixels = byte do joystick).
Compara fases 1 e 2 do gerador em -O0 e -O2 (o resultado precisa ser idêntico)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
RT = os.path.join(PROJ, "runtime")
SRCS = [os.path.join(RT, "src", s) for s in ("lx_mem.c", "lx_dispatch.c", "lx_overlay.c", "lx_alu.c", "lx_video.c",
                                              "lx_mikey.c", "lx_suzy_min.c", "lx_machine.c")]
SRCS += [os.path.join(RT, "platform", "host", s) for s in ("lx_platform_host.c", "lx_host_main.c")]


def expand5(v):
    return (v << 1) | (v >> 3)


def rgb888(pen):
    r, g, b = expand5(15 - pen), expand5(pen), expand5(pen)         # vermelho 15-p, verde p, azul p
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


def expected(joy):
    px = []
    for y in range(102):
        row = []
        for x in range(160):
            pen = x // 10
            if y == 0 and x < 2:
                pen = (joy >> 4) if x == 0 else (joy & 0x0F)         # o 1º byte do framebuffer = joystick
            row.append(rgb888(pen))
        px.append(row)
    return px


def read_ppm(path):
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(b"\n", 3)
    assert parts[0] == b"P6" and parts[1] == b"160 102" and parts[2] == b"255", parts[:3]
    raw = parts[3]
    return [[tuple(raw[(y * 160 + x) * 3:(y * 160 + x) * 3 + 3]) for x in range(160)] for y in range(102)]


@unittest.skipUnless(shutil.which("gcc"), "gcc ausente")
class TestDemoHost(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.mkdtemp()
        env = dict(os.environ, PYTHONPATH=os.path.join(PROJ, "pc-tools", "lynx2c"))
        subprocess.run([sys.executable, os.path.join(PROJ, "games", "demo_bars", "demo.py"), os.path.join(cls.td, "demo.o")],
                       check=True, capture_output=True)
        cls.exes = {}
        for phase in (1, 2):
            d = os.path.join(cls.td, "p%d" % phase)
            subprocess.run([sys.executable, "-m", "lynx2c", "build", "--file", os.path.join(cls.td, "demo.o"), "--name", "demo",
                            "--out-dir", d, "--phase", str(phase)], check=True, capture_output=True, env=env)
            for opt in ("-O0", "-O2"):
                exe = os.path.join(d, "demo%s" % opt)
                cc = subprocess.run(["gcc", "-std=c89", "-pedantic", "-Wall", "-Wextra", "-Werror", opt, "-I", os.path.join(RT, "include"),
                                     os.path.join(d, "demo_gen.c"), os.path.join(d, "demo_image.c")] + SRCS + ["-o", exe],
                                    capture_output=True, text=True)
                assert cc.returncode == 0, cc.stderr[:1500]
                cls.exes[(phase, opt)] = exe

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.td, ignore_errors=True)

    def run_demo(self, key, joy, frames=8, dump=6):
        out = os.path.join(self.td, "o_%d%s_%02X.ppm" % (key[0], key[1], joy))
        r = subprocess.run([self.exes[key], str(frames), str(dump), out, "%02X" % joy], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return read_ppm(out), r.stdout

    def test_image_matches_independent_expectation_in_all_configurations(self):
        for key in sorted(self.exes):
            for joy in (0x00, 0xA5, 0xFF):
                img, _ = self.run_demo(key, joy)
                self.assertEqual(img, expected(joy), "fase %d %s joy=%02X" % (key[0], key[1], joy))

    def test_no_sprites_requested_by_the_demo(self):
        _, out = self.run_demo((2, "-O0"), 0)
        self.assertIn("sprgo_ignorados=0", out)

    def test_frame_before_dma_is_black(self):
        out = os.path.join(self.td, "early.ppm")
        subprocess.run([self.exes[(2, "-O0")], "1", "0", out, "0"], check=True, capture_output=True)
        img = read_ppm(out)
        self.assertTrue(all(p == (0, 0, 0) for row in img for p in row))        # DMA ainda desligado no 1º quadro

    def test_joystick_value_is_read_from_the_register(self):
        a, _ = self.run_demo((2, "-O2"), 0x12)
        self.assertEqual(a[0][0], rgb888(0x1))
        self.assertEqual(a[0][1], rgb888(0x2))


if __name__ == "__main__":
    unittest.main()
