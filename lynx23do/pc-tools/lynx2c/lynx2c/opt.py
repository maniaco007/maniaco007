"""Estágio E (parcial): vivacidade de flags (análise reversa) em bloco reto.

Um flag definido por uma operação é MORTO se for redefinido adiante antes de
qualquer leitura (ou seja, ninguém observa o valor). Operações cujos flags
mortos não precisam ser materializados geram menos código — a otimização mais
valiosa do tradutor (docs/02 §3 estágio E).

Premissas conservadoras:
  - bloco reto isolado (flag_liveness): na SAÍDA, todos os flags N Z C V estão vivos;
  - com CFG (cfg_liveness): na saída de um bloco, live_out = união dos live_in dos sucessores
    ESTÁTICOS; se o fluxo sai por destino desconhecido (RTS, JMP indireto, JSR — o chamado pode
    ler flags —, alvo fora da imagem), TODOS os flags ficam vivos;
  - D (decimal) e demais flags nunca são "definidos" aqui (SED/CLD não suportados),
    portanto D é sempre live-in e não entra na análise;
  - PHP (futuro) deve declarar uses = NZCV; interrupções observam P só via pilha, o que
    jamais é lido por código de jogo corretamente escrito para flags que ele redefine antes de usar.
"""

from typing import Dict, Iterable, List

from .cfg import Cfg
from .ir import IrOp

ALL_FLAGS = frozenset("NZCV")


def flag_liveness(ops: List[IrOp], live_out: Iterable = ALL_FLAGS) -> List[IrOp]:
    live = frozenset(live_out)
    for op in reversed(ops):
        op.dead = op.defs - live
        live = (live - op.defs) | (op.uses & ALL_FLAGS)
    return ops


def _live_in(ops: List[IrOp], live_out) -> frozenset:
    live = frozenset(live_out)
    for op in reversed(ops):
        live = (live - op.defs) | (op.uses & ALL_FLAGS)
    return live


def cfg_liveness(cfg: Cfg, ops_by_block: Dict[int, List[IrOp]], precise_exits: bool = False) -> Dict[int, frozenset]:
    """Ponto fixo de vivacidade de flags sobre o CFG; marca op.dead em cada bloco.
    Retorna live_in por bloco (também guardado em cfg.live_in).

    GARANTIA e LIMITE (flags N,Z,C,V):
      - precise_exits=False (padrão): um flag morto na saída de um bloco pode conter valor
        DESATUALIZADO nesse ponto; como o código seguinte o redefine antes de lê-lo, o programa não
        observa a diferença — EXCETO via P empilhado por IRQ (lx_sched_service) ou por PHP (que declara
        uses=NZCV e portanto força vivacidade). O P empilhado pode divergir do hardware nos flags mortos.
      - precise_exits=True: todo flag é vivo na saída de TODO bloco => P exato em qualquer fronteira de
        bloco (onde IRQs são entregues), ao custo de eliminar só flags mortos DENTRO do bloco.
    """
    live_in = {s: frozenset() for s in cfg.blocks}

    def live_out(b):
        if precise_exits:
            return ALL_FLAGS
        if b.kind in ("jump_ind", "ret", "call"):
            return ALL_FLAGS
        out = frozenset()
        for s in b.succs:
            out |= live_in[s] if s in cfg.blocks else ALL_FLAGS
        return out

    changed = True
    while changed:                         # monotônico: converge em poucas iterações
        changed = False
        for start in cfg.starts:
            li = _live_in(ops_by_block[start], live_out(cfg.blocks[start]))
            if li != live_in[start]:
                live_in[start] = li
                changed = True
    for start in cfg.starts:
        flag_liveness(ops_by_block[start], live_out(cfg.blocks[start]))
    cfg.live_in = live_in
    return live_in
