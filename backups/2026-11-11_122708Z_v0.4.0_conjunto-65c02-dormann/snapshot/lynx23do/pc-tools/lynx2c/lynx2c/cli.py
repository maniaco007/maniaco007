"""CLI mínima do lynx2c (v0.2.0): traduz bytes brutos em um bloco reto.

  python3 -m lynx2c translate --org 0x0200 --hex "A9 01 D0 02 69 02 60" [--entry 0x0200]... [--overlay-id 0]
  python3 -m lynx2c disasm    --org 0x0200 --hex "A9 01 69 02"      (varredura linear: diagnóstico)
  python3 -m lynx2c cfg       --org 0x0200 --hex "..."               (blocos e sucessores)
  python3 -m lynx2c translate --org 0x0200 --file codigo.bin --out gen.c

translate: descida recursiva a partir das entradas (padrão: --org); só o alcançável é traduzido.

(Executar com PYTHONPATH=pc-tools/lynx2c.)
"""

import argparse
import sys

from . import __version__
from .decode import DecodeError, decode_block
from .emit_c import emit_overlay
from .pipeline import analyze


from .emit_c import _HEADER as _H0
from . import ABI_VERSION

_HDR = _H0 % {"ver": __version__, "abi": ABI_VERSION} + "\n"


def _int(s):
    return int(s, 0)


def _load_bytes(args) -> bytes:
    if args.hex is not None:
        try:
            return bytes.fromhex(args.hex.replace("$", "").replace(",", " "))
        except ValueError as e:
            raise SystemExit("erro: --hex inválido: %s" % e)
    with open(args.file, "rb") as f:
        return f.read()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="lynx2c", description=__doc__.split("\n")[0])
    p.add_argument("--version", action="version", version="lynx2c " + __version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("translate", "disasm", "cfg"):
        s = sub.add_parser(name)
        s.add_argument("--org", type=_int, default=0x0200, help="endereço 65C02 do primeiro byte")
        g = s.add_mutually_exclusive_group(required=True)
        g.add_argument("--hex")
        g.add_argument("--file")
        if name in ("translate", "cfg"):
            s.add_argument("--entry", type=_int, action="append", default=None,
                           help="entrada adicional (repetível); padrão: --org")
            s.add_argument("--hook", type=_int, action="append", default=None, metavar="ADDR",
                           help="rotina substituída por hook HLE no runtime: não é decodificada (repetível)")
            s.add_argument("--smc-operand", type=_int, action="append", default=None, metavar="ADDR",
                           help="byte de operando IMEDIATO modificado em execução (repetível; param_operand)")
        if name == "translate":
            s.add_argument("--overlay-id", type=int, default=0)
            s.add_argument("--precise-exits", action="store_true",
                           help="todos os flags vivos em toda saída de bloco (P exato em IRQ/yield)")
            s.add_argument("--out", default="-")
    a = p.parse_args(argv)

    data = _load_bytes(a)
    if a.cmd == "disasm":
        try:
            insns = decode_block(data, a.org)
        except DecodeError as e:
            print("erro: %s" % e, file=sys.stderr)
            return 2
        for i in insns:
            print("$%04X  %-18s %d ciclos" % (i.addr, i.text(), i.cycles))
        return 0

    entries = a.entry or [a.org]
    try:
        cfg, ops = analyze(data, a.org, entries, getattr(a, "precise_exits", False), a.smc_operand or (), a.hook or ())
    except (DecodeError, ValueError) as e:
        print("erro: %s" % e, file=sys.stderr)
        return 2

    if a.cmd == "cfg":
        for s in cfg.starts:
            b = cfg.blocks[s]
            print("$%04X  %-8s%s  %d insn  -> %s" % (s, b.kind, " (ret-addr)" if b.retaddr else "",
                  len(b.insns), " ".join("$%04X" % x for x in b.succs) or "-"))
        return 0

    code = emit_overlay(a.overlay_id, cfg, ops)
    code = _HDR + code
    if a.out == "-":
        sys.stdout.write(code)
    else:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
