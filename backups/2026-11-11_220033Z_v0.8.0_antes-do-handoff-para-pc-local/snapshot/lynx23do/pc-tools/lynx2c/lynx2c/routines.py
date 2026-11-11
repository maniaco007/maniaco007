"""Fase 2 do gerador: partição do CFG em ROTINAS (uma função C por rotina, vários blocos fundidos por goto).

Definições
  raiz        bloco que inicia uma função C. É ponto de entrada "de verdade" do trampolim.
  rotina      raiz + todos os blocos alcançáveis a partir dela por arestas INTRA-rotina:
              fall-through, desvio condicional, BRA/JMP abs. Arestas que chegam a OUTRA raiz são SAÍDAS
              (a função devolve o PC e o trampolim despacha).
  sub-entrada qualquer líder da rotina pode ser retomado por (função, sub): é como um YIELD no meio da rotina
              (e um alvo dinâmico para dentro dela) continua dali. Por isso a tabela de despacho lista TODOS os líderes.

Raízes (algoritmo, determinístico):
  1. entradas/sementes do CFG;  2. alvos de JSR;  3. continuações de JSR e de BRK (alvos de RTS/RTI dinâmicos);
  4. fixpoint: todo bloco alcançável a partir de >= 2 raízes vira raiz também (evita duplicar código).
Blocos que terminam em JSR, RTS, RTI, BRK ou JMP indireto não têm arestas intra-rotina (a função sai).
"""
from typing import Dict, List, Set

from .cfg import Cfg

# Limite padrão de blocos por rotina. MEDIDO no Dormann 6502 (docs/04 §3.4): sem limite 25,4x e quadro de pilha de 15 360 B;
# com 32 blocos 17,7x e quadro de 44 B (64 blocos: 17,2x; 16: 18,5x). Passa de 0 = sem limite para testes.
DEFAULT_MAX_BLOCKS = 32

_INTRA_KINDS = ("fall", "branch", "jump")        # tipos de bloco com sucessores intra-rotina


def _intra_succs(cfg: Cfg, start: int) -> List[int]:
    b = cfg.blocks[start]
    if b.kind not in _INTRA_KINDS:
        return []
    return [s for s in b.succs if s in cfg.blocks]


def _reach(cfg: Cfg, root: int, roots: Set[int]) -> List[int]:
    seen, work = {root}, [root]
    while work:
        a = work.pop()
        for s in _intra_succs(cfg, a):
            if s not in seen and s not in roots:
                seen.add(s)
                work.append(s)
    return sorted(seen)


def partition(cfg: Cfg, max_blocks: int = DEFAULT_MAX_BLOCKS) -> Dict[int, List[int]]:
    """Retorna {raiz: [blocos da rotina em ordem de endereço]} (a raiz também está na lista).

    max_blocks > 0: rotinas maiores que isso são quebradas (novas raízes a cada 'max_blocks' blocos, em ordem de
    endereço). Motivo MEDIDO (docs/04 §3.4): numa função com dezenas de blocos as ~16 variáveis vivas não cabem nos ~12
    registradores do ARM e ~27% das instruções viram spill/reload; escopos menores reduzem a pressão."""
    roots: Set[int] = {e for e in cfg.entries if e in cfg.blocks}
    for b in cfg.blocks.values():
        if b.kind == "call":
            if b.succs[0] in cfg.blocks:
                roots.add(b.succs[0])                      # alvo do JSR
        if b.retaddr:
            roots.add(b.start)                             # continuação de JSR/BRK
    while True:
        if max_blocks > 0:
            grew = False
            for r in sorted(roots):
                blks = _reach(cfg, r, roots)
                if len(blks) > max_blocks:
                    for extra in blks[max_blocks::max_blocks]:
                        if extra not in roots:
                            roots.add(extra)
                            grew = True
            if grew:
                continue
        owners: Dict[int, Set[int]] = {}
        for r in sorted(roots):
            for blk in _reach(cfg, r, roots):
                owners.setdefault(blk, set()).add(r)
        multi = {blk for blk, rs in owners.items() if len(rs) > 1 and blk not in roots}
        if not multi:
            break
        roots |= multi
    # blocos que nenhuma raiz alcança (não deveria ocorrer): viram raízes para não ficarem sem código
    covered = {blk for r in roots for blk in _reach(cfg, r, roots)}
    for blk in cfg.starts:
        if blk not in covered:
            roots.add(blk)
    return {r: _reach(cfg, r, roots) for r in sorted(roots)}


def roots_of(cfg: Cfg, max_blocks: int = DEFAULT_MAX_BLOCKS) -> Set[int]:
    return set(partition(cfg, max_blocks))
