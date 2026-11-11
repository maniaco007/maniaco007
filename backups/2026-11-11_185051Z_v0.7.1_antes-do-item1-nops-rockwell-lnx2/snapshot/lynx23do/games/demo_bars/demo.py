"""demo_bars — homebrew de TESTE em 65C02 (BS93) que usa o caminho de um jogo real, sem Suzy/IRQ:

  1. programa a PALETA pelos registradores do Mikey (GREENn / BLUEREDn): pen p = verde p, vermelho 15-p, azul p;
  2. preenche o FRAMEBUFFER em $C000 (80 bytes x 102 linhas) com 16 barras verticais de 10 pixels (pen = x / 10);
  3. liga o DMA de vídeo (DISPADR = $C000, DISPCTL = $09);
  4. laço eterno: lê o JOYSTICK ($FCB0) e grava o valor no 1º byte do framebuffer (os 2 primeiros pixels da linha 0
     mostram os bits do controle: nibble alto = pixel 0, nibble baixo = pixel 1).

Uso: python3 games/demo_bars/demo.py <saida.o>      (gera o arquivo BS93)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pc-tools", "lynx2c"))
from lynx2c.asm import assemble          # noqa: E402
from lynx2c.ingest import build_bs93     # noqa: E402

LOAD = 0x0200            # endereço do 1º byte de código (o cabeçalho BS93 de 10 bytes fica logo antes)
FB = 0xC000


def program():
    tab = [(i // 5) * 17 for i in range(80)]            # byte i = 2 pixels do pen i // 5  ->  barras de 10 px
    items = [
        ("L", "start"),
        ("LDX", "imm", 15),
        ("L", "pal"),
        ("TXA",), ("STA", "absx", 0xFDA0),               # GREEN[x] = x
        ("TXA",), ("EOR", "imm", 0x0F), ("STA", "zp", 0x10),   # vermelho = 15 - x
        ("TXA",), ("ASL", "acc"), ("ASL", "acc"), ("ASL", "acc"), ("ASL", "acc"),   # azul = x (nibble alto)
        ("ORA", "zp", 0x10), ("STA", "absx", 0xFDB0),
        ("DEX",), ("BPL", "rel", "pal"),
        ("LDA", "imm", FB & 0xFF), ("STA", "zp", 0x20), ("LDA", "imm", FB >> 8), ("STA", "zp", 0x21),
        ("LDX", "imm", 102),
        ("L", "line"),
        ("LDY", "imm", 0),
        ("L", "col"),
        ("LDA", "absy", "tab"), ("STA", "izy", 0x20), ("INY",), ("CPY", "imm", 80), ("BNE", "rel", "col"),
        ("CLC",), ("LDA", "zp", 0x20), ("ADC", "imm", 80), ("STA", "zp", 0x20),
        ("LDA", "zp", 0x21), ("ADC", "imm", 0), ("STA", "zp", 0x21),
        ("DEX",), ("BNE", "rel", "line"),
        ("LDA", "imm", FB & 0xFF), ("STA", "abs", 0xFD94),
        ("LDA", "imm", FB >> 8), ("STA", "abs", 0xFD95),
        ("LDA", "imm", 0x09), ("STA", "abs", 0xFD92),
        ("L", "main"),
        ("LDA", "abs", 0xFCB0), ("STA", "abs", FB), ("JMP", "abs", "main"),
        ("L", "tab"), ("DB", tab),
    ]
    items = [it if it[0] in ("L", "DB") or len(it) == 3 else (it[0], "imp") if it[0] not in ("ASL",) else it for it in items]
    return assemble(LOAD, items)


def main():
    code, labels = program()
    out = sys.argv[1] if len(sys.argv) > 1 else "demo.o"
    with open(out, "wb") as f:
        f.write(build_bs93(code, LOAD))
    print("%s: %d bytes de código, tab em $%04X" % (out, len(code), labels["tab"]))


if __name__ == "__main__":
    main()
