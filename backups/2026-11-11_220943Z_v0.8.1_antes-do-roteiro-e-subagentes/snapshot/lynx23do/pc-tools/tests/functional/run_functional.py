"""Executa uma imagem flat de 64 KB pelo pipeline COMPLETO (lynx2c -> C89 -> gcc -> lx_run) com sementes
iterativas: cada PC não resolvido em tempo de execução vira nova entrada e o código é retraduzido.

  python3 run_functional.py <imagem.bin> --entry 0x0400 --success 0x3469 [--max-cycles 300000000]
                            [--cc-opt -O1] [--workdir DIR] [--precise-exits]

Resultado (saída e código de retorno): PASSOU (trap em --success), FALHOU (trap noutro PC) ou erro.
A imagem é DADO de terceiros: só é lida como bytes (nunca executada pelo Python).
Executar com PYTHONPATH=pc-tools/lynx2c.
"""
import argparse
import os
import re
import subprocess
import sys
import time

from lynx2c import ABI_VERSION, __version__
from lynx2c.emit_c import _HEADER, emit_overlay
from lynx2c.pipeline import analyze

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--entry", type=lambda s: int(s, 0), default=0x0400)
    ap.add_argument("--success", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--max-cycles", type=int, default=400_000_000)
    ap.add_argument("--cc-opt", default="-O1")
    ap.add_argument("--workdir", default=os.path.join(PROJ, "build", "functional"))
    ap.add_argument("--precise-exits", action="store_true")
    ap.add_argument("--max-blocks", type=int, default=None, help="blocos por rotina na fase 2 (padrão: DEFAULT_MAX_BLOCKS; 0 = sem limite)")
    ap.add_argument("--phase", type=int, choices=(1, 2), default=2, help="fase do gerador (1: bloco por função; 2: rotinas fundidas)")
    ap.add_argument("--max-rounds", type=int, default=60)
    ap.add_argument("--smc-operand", type=lambda s: int(s, 0), action="append", default=[], metavar="ADDR",
                    help="byte de operando IMEDIATO modificado em execução (param_operand); repetível")
    ap.add_argument("--report", metavar="ARQUIVO.md", help="escreve o relatório de elegibilidade da última rodada (mede ARM com clang)")
    ap.add_argument("--skip", action="append", default=[], metavar="DE:PARA",
                    help="hook HLE que pula um trecho auto-modificável: PC DE desvia para PARA (até 4)")
    a = ap.parse_args()

    os.makedirs(a.workdir, exist_ok=True)
    with open(a.image, "rb") as f:
        image = f.read()
    if len(image) > 0x10000:
        sys.exit("imagem maior que 64 KB")
    seeds = {a.entry} | {int(x.split(':')[0], 0) for x in a.skip}   # hook exige fronteira de bloco no PC de origem
    inc = "-I" + os.path.join(PROJ, "runtime", "include")
    srcs = [os.path.join(PROJ, "runtime", "src", s) for s in ("lx_mem.c", "lx_dispatch.c", "lx_overlay.c", "lx_alu.c")]
    srcs += [os.path.join(PROJ, "pc-tools", "tests", "harness", "lx_test_stubs.c"), os.path.join(HERE, "functional_main.c")]

    for rnd in range(1, a.max_rounds + 1):
        t0 = time.time()
        cfg, ops = analyze(image, 0, sorted(seeds), a.precise_exits, a.smc_operand,
                           hooks={int(x.split(':')[0], 0) for x in a.skip})
        c_path = os.path.join(a.workdir, "functional_gen.c")
        with open(c_path, "w", encoding="utf-8") as f:
            f.write(_HEADER % {"ver": __version__, "abi": ABI_VERSION} + "\n" + emit_overlay(0, cfg, ops, phase=a.phase, max_blocks=a.max_blocks))
        exe = os.path.join(a.workdir, "functional_harness")
        defs = []
        for i, sk in enumerate(a.skip[:4]):
            frm, to = (int(x, 0) for x in sk.split(":"))
            defs += ["-DSKIP%d_FROM=0x%04X" % (i, frm), "-DSKIP%d_TO=0x%04X" % (i, to)]
        cc = sh(["gcc", "-std=c89", "-pedantic", "-Wall", "-Wextra", "-Werror", a.cc_opt, inc] + defs + [c_path] + srcs + ["-o", exe])
        if cc.returncode:
            print(cc.stderr[:2000])
            sys.exit("falha de compilação")
        t1 = time.time()
        run = sh([exe, a.image, "%X" % a.entry, str(a.max_cycles)])
        out = run.stdout.strip()
        n_insn = sum(len(b.insns) for b in cfg.blocks.values())
        print("rodada %2d: %5d blocos, %6d instruções, tradução+compilação %.1fs, execução %.1fs -> %s" % (
            rnd, len(cfg.blocks), n_insn, t1 - t0, time.time() - t1, out or run.stderr.strip()[:200]))
        m = re.match(r"UNRESOLVED pc=\$([0-9A-F]{4})", out)
        if m:
            pc = int(m.group(1), 16)
            if pc in seeds or pc >= len(image):
                sys.exit("PC não resolvido fora da imagem ou já semeado: $%04X" % pc)
            seeds.add(pc)
            continue
        m = re.match(r"TRAP pc=\$([0-9A-F]{4})", out)
        if m and a.report:
            from lynx2c.report import build_report
            rep = build_report(os.path.basename(a.image), cfg, ops, len(image), include_dir=os.path.join(PROJ, "runtime", "include"),
                               phase=a.phase, max_blocks=a.max_blocks, smc_operands=a.smc_operand, hooks={int(x.split(':')[0], 0) for x in a.skip},
                               notes=["imagem funcional com %d sementes dinâmicas descobertas em execução" % (len(seeds) - 1 - len(a.skip))])
            with open(a.report, "w", encoding="utf-8") as f:
                f.write(rep)
            print("relatório: %s" % a.report)
        if m:
            pc = int(m.group(1), 16)
            ok = pc == a.success
            print("%s: trap em $%04X (esperado sucesso em $%04X)%s" % (
                "PASSOU" if ok else "FALHOU", pc, a.success,
                "  [trechos dispensados por hook: %s]" % ", ".join(a.skip) if a.skip else ""))
            sys.exit(0 if ok else 1)
        sys.exit("resultado inesperado: %r" % out)
    sys.exit("limite de rodadas de semeadura atingido")


if __name__ == "__main__":
    main()
