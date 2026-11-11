"""CLI mínima do lynx2c (v0.2.0): traduz bytes brutos em um bloco reto.

  python3 -m lynx2c translate --org 0x0200 --hex "A9 01 69 02 85 10" --name lx_ov00_0200
  python3 -m lynx2c disasm    --org 0x0200 --hex "A9 01 69 02"
  python3 -m lynx2c translate --org 0x0200 --file bloco.bin --out gen.c

(Executar com PYTHONPATH=pc-tools/lynx2c.)
"""

import argparse
import sys

from . import __version__
from .decode import DecodeError, decode_block
from .emit_c import emit_unit
from .lift import lift
from .opt import flag_liveness


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
    for name in ("translate", "disasm"):
        s = sub.add_parser(name)
        s.add_argument("--org", type=_int, default=0x0200, help="endereço 65C02 do primeiro byte")
        g = s.add_mutually_exclusive_group(required=True)
        g.add_argument("--hex")
        g.add_argument("--file")
        if name == "translate":
            s.add_argument("--name", default=None)
            s.add_argument("--out", default="-")
    a = p.parse_args(argv)

    data = _load_bytes(a)
    try:
        insns = decode_block(data, a.org)
    except DecodeError as e:
        print("erro: %s" % e, file=sys.stderr)
        return 2

    if a.cmd == "disasm":
        for i in insns:
            print("$%04X  %-14s %d ciclos" % (i.addr, i.text(), i.cycles))
        return 0

    ops = flag_liveness(lift(insns))
    name = a.name or ("lx_blk_%04x" % a.org)
    code = emit_unit([(name, ops, a.org)])
    if a.out == "-":
        sys.stdout.write(code)
    else:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
