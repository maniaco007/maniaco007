"""report.md — relatório de elegibilidade de um jogo (docs/02 estágio C; critério objetivo de docs/04 §3).

Responde, ANTES de qualquer tentativa de portar: quanto código 65C02 é alcançável, quanto ele vira em ARM
(medido de verdade com clang -> ARM big-endian quando disponível) e se cabe no orçamento de código.
"""
import os
import tempfile
from collections import Counter
from typing import Iterable, Optional

from . import ABI_VERSION, __version__
from . import armsize
from .emit_c import _HEADER, emit_overlay
from .ir import region_of

# Fator medido (suítes de Dormann, fase 1, clang -Os ARM BE): ver docs/04 §3.1.
# Só é usado como ESTIMATIVA (e rotulado assim) quando não há clang para medir o jogo de fato.
REFERENCE_EXPANSION_PHASE1 = 27.0     # bytes ARM por byte de 65C02 (fase 1, ABI v2): MEDIDO nas suítes Dormann, docs/04 §3.1

_NO_MEM_MODES = {"imm", "imp", "acc", "rel", "brk"}


def _pct(a, b):
    return "%.1f%%" % (100.0 * a / b) if b else "n/d"


def build_report(title, cfg, ops_by_block, image_len, include_dir: Optional[str] = None, arm_opt: str = "-Os",
                 budget_kb: int = 640, smc_operands: Iterable[int] = (), hooks: Iterable[int] = (),
                 notes: Iterable[str] = (), measure: bool = True) -> str:
    smc_operands, hooks = sorted(smc_operands), sorted(hooks)
    blocks = [cfg.blocks[s] for s in cfg.starts]
    insns = [i for b in blocks for i in b.insns]
    n_insn, code_bytes = len(insns), sum(i.length for i in insns)
    kinds = Counter(b.kind for b in blocks)
    mn = Counter(i.mnemonic for i in insns)

    # flags: definições x eliminadas pela vivacidade
    defs = sum(len(o.defs) for v in ops_by_block.values() for o in v)
    dead = sum(len(o.dead) for v in ops_by_block.values() for o in v)

    # acessos a memória por região
    reg = Counter()
    for v in ops_by_block.values():
        for o in v:
            ins = o.insn
            if ins.mode in _NO_MEM_MODES or o.region == "NONE":
                continue
            if ins.mode in ("zp", "zpx", "zpy"):
                reg["RAM (página zero)"] += 1
            elif o.region == "DYNAMIC":
                reg["dinâmico (indexado/indireto)"] += 1
            else:
                reg[{"RAM": "RAM (absoluto)", "SUZY": "Suzy $FC00-FCFF", "MIKEY": "Mikey $FD00-FDFF",
                     "ROMVEC": "ROM/vetores $FE00+"}[o.region]] += 1

    ext = sorted({s for b in blocks for s in b.succs if s not in cfg.blocks and s not in set(hooks)})
    dyn = kinds["jump_ind"] + kinds["ret"] + kinds["brk"]

    # ---- medição ARM ----
    arm = None
    note_arm = ""
    if measure and include_dir and armsize.available():
        with tempfile.TemporaryDirectory() as td:
            c_path = os.path.join(td, "gen.c")
            with open(c_path, "w", encoding="utf-8") as f:
                f.write(_HEADER % {"ver": __version__, "abi": ABI_VERSION} + "\n" + emit_overlay(0, cfg, ops_by_block))
            arm = armsize.measure_c(c_path, include_dir, arm_opt)
    elif measure:
        note_arm = "clang/llvm-size indisponíveis: tamanho ARM ESTIMADO pelo fator de referência."

    L = ["# Relatório de elegibilidade — %s" % title, "",
         "_Gerado por lynx2c %s. Fase 1 do gerador (registradores em `LxCpu`); a fase 2 deve reduzir os números de ARM._" % __version__, "",
         "## Código alcançável", "",
         "| Item | Valor |", "|---|---:|",
         "| Imagem analisada | %d bytes |" % image_len,
         "| Blocos básicos | %d |" % len(blocks),
         "| Instruções 65C02 alcançadas | %d |" % n_insn,
         "| **Bytes de código 65C02 alcançados** | **%d** (%s da imagem; o resto é dado ou não alcançado) |" % (code_bytes, _pct(code_bytes, image_len)),
         "| Instruções por bloco (média) | %.2f |" % (n_insn / len(blocks) if blocks else 0),
         "| Continuações de JSR/BRK (alvos de RTS/RTI dinâmicos) | %d |" % sum(1 for b in blocks if b.retaddr),
         "| Saídas dinâmicas (RTS, RTI, JMP indireto, BRK) | %d |" % dyn,
         "| Sucessores fora do código conhecido | %d |" % len(ext), ""]
    L += ["Blocos por tipo: " + ", ".join("%s=%d" % kv for kv in sorted(kinds.items())), "",
          "Mnemônicos mais frequentes: " + ", ".join("%s %d" % kv for kv in mn.most_common(10)), ""]
    if ext:
        L += ["Sucessores fora do código conhecido (semente/overlay/hook necessário): " +
              ", ".join("$%04X" % a for a in ext[:12]) + (" …" if len(ext) > 12 else ""), ""]

    L += ["## Flags e memória", "",
          "- Definições de flags N/Z/C/V: %d; **eliminadas pela vivacidade: %d (%s)**." % (defs, dead, _pct(dead, defs)),
          "- Acessos a memória por região: " + (", ".join("%s %d" % kv for kv in sorted(reg.items())) or "nenhum"), ""]

    L += ["## Orçamento de código ARM (docs/04)", ""]
    budget = budget_kb * 1024
    if arm:
        tot = arm["text"] + arm["rodata"]
        exp = tot / code_bytes if code_bytes else 0
        ipi = arm["text"] / 4.0 / n_insn if n_insn else 0
        L += ["Medido com clang %s → ARM big-endian (ARM7TDMI, modo ARM):" % arm["opt"], "",
              "| Item | Valor |", "|---|---:|",
              "| `.text` (código + pools de literais) | %d bytes |" % arm["text"],
              "| Tabelas de despacho / dados constantes | %d bytes |" % arm["rodata"],
              "| **Total ARM** | **%d bytes (%.1f KB)** |" % (tot, tot / 1024.0),
              "| Expansão (bytes ARM por byte de código 65C02) | **%.1f×** |" % exp,
              "| Instruções ARM por instrução 65C02 (aprox.) | %.1f |" % ipi,
              "| Orçamento de código (`[budget] max_code_kb`) | %d KB |" % budget_kb, ""]
        fits = tot <= budget
        L += ["**Veredito de tamanho: %s** — usa %.0f%% do orçamento; nesta expansão cabem ~%.0f KB de código 65C02 alcançado." % (
            "CABE" if fits else "NÃO CABE", 100.0 * tot / budget, budget / exp / 1024.0 if exp else 0), ""]
    else:
        est = code_bytes * REFERENCE_EXPANSION_PHASE1
        L += [note_arm or "Medição ARM não solicitada.", "",
              "ESTIMATIVA (fator de referência %.0f× da fase 1): ~%.1f KB de ARM para %d bytes de 65C02; orçamento %d KB → %s." % (
                  REFERENCE_EXPANSION_PHASE1, est / 1024.0, code_bytes, budget_kb, "cabe" if est <= budget else "NÃO cabe"), ""]

    L += ["## Avisos", ""]
    w = []
    if smc_operands:
        w.append("SMC de operando imediato (`param_operand`) em: " + ", ".join("$%04X" % a for a in smc_operands) + ".")
    if hooks:
        w.append("Rotinas substituídas por hook (não traduzidas): " + ", ".join("$%04X" % a for a in hooks) + ".")
    if dyn:
        w.append("Há %d saídas dinâmicas: alvos só conhecidos em execução exigem o perfil dinâmico (lynxtrace) ou sementes." % dyn)
    w += list(notes)
    L += ["- " + x for x in w] or ["- nenhum"]
    L += ["", "## O que este relatório NÃO diz", "",
          "- Só o código ALCANÇÁVEL a partir das entradas dadas: código só atingido por alvos dinâmicos não vistos fica de fora (subestima).",
          "- Tamanho, não desempenho: o orçamento de CPU (~6 instruções ARM por instrução 65C02, docs/01 §6) é outra conta.",
          "- Não cobre dados (sprites, tabelas) nem a RAM do cartucho: ver o orçamento total em docs/04 §2.", ""]
    return "\n".join(L)
