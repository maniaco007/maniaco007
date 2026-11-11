"""CLI mínima do lynx2c (v0.2.0): traduz bytes brutos em um bloco reto.

  python3 -m lynx2c translate --org 0x0200 --hex "A9 01 D0 02 69 02 60" [--entry 0x0200]... [--overlay-id 0]
  python3 -m lynx2c disasm    --org 0x0200 --hex "A9 01 69 02"      (varredura linear: diagnóstico)
  python3 -m lynx2c cfg       --org 0x0200 --hex "..."               (blocos e sucessores)
  python3 -m lynx2c translate --org 0x0200 --file codigo.bin --out gen.c
  python3 -m lynx2c ingest    --file jogo.lnx|programa.o|imagem.bin [--org 0x0200]   (estágio A: formato e metadados)
  python3 -m lynx2c report    --file programa.o [--budget-kb 640] [--out report.md]  (elegibilidade; BS93 ou --org)

translate: descida recursiva a partir das entradas (padrão: --org); só o alcançável é traduzido.

(Executar com PYTHONPATH=pc-tools/lynx2c.)
"""

import argparse
import os
import sys

from . import __version__
from .decode import DecodeError, decode_block
from .emit_c import emit_overlay
from .ingest import IngestError, ingest
from .pipeline import analyze
from .report import build_report


from .emit_c import _HEADER as _H0
from . import ABI_VERSION

_HDR = _H0 % {"ver": __version__, "abi": ABI_VERSION} + "\n"


_org_given = False


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


def _ingest_cmds(a, data) -> int:
    try:
        info = ingest(data, org=a.org if _org_given else None)
    except IngestError as e:
        print("erro: %s" % e, file=sys.stderr)
        return 2
    print("formato: %s | sha256: %s | %d bytes" % (info.kind, info.sha256, info.size))
    if info.kind == "lnx":
        print("nome: %r | fabricante: %r | rotação: %s | AUDIN: %s | EEPROM: %d" % (
            info.name, info.manufacturer, info.rotation, info.audin, info.eeprom))
        print("banco 0: %d KB | banco 1: %d KB" % (info.bank0_bytes // 1024, info.bank1_bytes // 1024))
    else:
        print("carga em $%04X, entrada $%04X, %d bytes" % (info.load_addr, info.entry, len(info.data)))
    for w in info.warnings:
        print("aviso: %s" % w)
    if a.cmd == "ingest":
        return 0
    if info.kind == "lnx":
        print("\nO código de um cartucho .lnx comercial não é conhecido sem executar a ROM de boot (1º bloco cifrado):\n"
              "use o perfil dinâmico (lynxtrace, a fazer) com a imagem de boot do usuário. Sem relatório de código.")
        return 0
    entries = a.entry or [info.entry]
    try:
        cfg, ops = analyze(info.data, info.load_addr, entries, False, a.smc_operand or (), a.hook or ())
    except (DecodeError, ValueError) as e:
        print("erro: %s" % e, file=sys.stderr)
        return 2
    inc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "runtime", "include")
    rep = build_report(a.file or "(hex)", cfg, ops, len(info.data), include_dir=inc, arm_opt=a.arm_opt,
                       budget_kb=a.budget_kb, smc_operands=a.smc_operand or (), hooks=a.hook or (),
                       notes=info.warnings, measure=not a.no_arm)
    if a.out == "-":
        sys.stdout.write("\n" + rep)
    else:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(rep)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="lynx2c", description=__doc__.split("\n")[0])
    p.add_argument("--version", action="version", version="lynx2c " + __version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("translate", "disasm", "cfg", "ingest", "report"):
        s = sub.add_parser(name)
        s.add_argument("--org", type=_int, default=None, help="endereço 65C02 do primeiro byte (padrão $0200; obrigatório p/ imagem plana em ingest/report)")
        g = s.add_mutually_exclusive_group(required=True)
        g.add_argument("--hex")
        g.add_argument("--file")
        if name == "report":
            s.add_argument("--budget-kb", type=int, default=640)
            s.add_argument("--arm-opt", default="-Os")
            s.add_argument("--out", default="-")
            s.add_argument("--no-arm", action="store_true", help="não medir com clang (usa o fator de referência)")
        if name in ("translate", "cfg", "report"):
            s.add_argument("--entry", type=_int, action="append", default=None,
                           help="entrada adicional (repetível); padrão: --org")
            s.add_argument("--hook", type=_int, action="append", default=None, metavar="ADDR",
                           help="rotina substituída por hook HLE no runtime: não é decodificada (repetível)")
            s.add_argument("--smc-operand", type=_int, action="append", default=None, metavar="ADDR",
                           help="byte de operando IMEDIATO modificado em execução (repetível; param_operand)")
        if name == "translate":
            s.add_argument("--overlay-id", type=int, default=0)
            s.add_argument("--phase", type=int, choices=(1, 2), default=2, help="1: um bloco por função; 2: rotinas fundidas (padrão)")
            s.add_argument("--max-blocks", type=int, default=None, help="blocos por rotina na fase 2 (0 = sem limite)")
            s.add_argument("--precise-exits", action="store_true",
                           help="todos os flags vivos em toda saída de bloco (P exato em IRQ/yield)")
            s.add_argument("--out", default="-")
    a = p.parse_args(argv)

    global _org_given
    _org_given = a.org is not None
    if a.org is None:
        a.org = 0x0200
    data = _load_bytes(a)
    if a.cmd in ("ingest", "report"):
        return _ingest_cmds(a, data)
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

    code = emit_overlay(a.overlay_id, cfg, ops, phase=a.phase, max_blocks=a.max_blocks)
    code = _HDR + code
    if a.out == "-":
        sys.stdout.write(code)
    else:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
