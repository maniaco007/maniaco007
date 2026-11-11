"""Estágio E (parcial): vivacidade de flags (análise reversa) em bloco reto.

Um flag definido por uma operação é MORTO se for redefinido adiante antes de
qualquer leitura (ou seja, ninguém observa o valor). Operações cujos flags
mortos não precisam ser materializados geram menos código — a otimização mais
valiosa do tradutor (docs/02 §3 estágio E).

Premissas conservadoras:
  - na SAÍDA do bloco, todos os flags N Z C V estão vivos (não há CFG ainda);
  - D (decimal) e demais flags nunca são "definidos" aqui (SED/CLD não suportados),
    portanto D é sempre live-in e não entra na análise.
"""

from typing import Iterable, List

from .ir import IrOp

ALL_FLAGS = frozenset("NZCV")


def flag_liveness(ops: List[IrOp], live_out: Iterable = ALL_FLAGS) -> List[IrOp]:
    live = frozenset(live_out)
    for op in reversed(ops):
        op.dead = op.defs - live
        live = (live - op.defs) | (op.uses & ALL_FLAGS)
    return ops
