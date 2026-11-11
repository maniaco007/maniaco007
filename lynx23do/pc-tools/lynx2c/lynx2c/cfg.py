"""Estágio C (parcial): grafo de fluxo de controle por descida recursiva sobre UMA imagem de código.

Regras (docs/02 §2–§3):
  - só decodifica o que é ALCANÇÁVEL a partir das entradas (bytes não alcançados = dados, nunca decodificados);
  - líderes de bloco = entradas ∪ alvos de desvio/salto/JSR ∪ instrução após desvio ∪ continuação após JSR;
  - opcode fora da tabela em caminho alcançável => erro EXPLÍCITO (não se adivinha, não se poda em silêncio);
  - instruções que se sobrepõem (salto desalinhado / SMC) => erro EXPLÍCITO (docs/02 §2 regra 4);
  - alvos fora da imagem são ACEITOS como saídas externas (outro overlay / dinâmico): viram sucessor
    desconhecido (o runtime os trata via lx_dispatch / lx_unresolved).
Determinístico: tudo ordenado por endereço.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set

from .decode import DecodeError, Insn, decode_one


class OverlapError(DecodeError):
    def __init__(self, addr, other):
        super().__init__("instrução em $%04X sobrepõe a de $%04X (salto desalinhado ou código "
                         "auto-modificável): exige decisão no manifest" % (addr, other))
        self.addr, self.other = addr, other


@dataclass
class Block:
    start: int
    insns: List[Insn]
    kind: str                     # 'fall' | 'branch' | 'jump' | 'jump_ind' | 'call' | 'ret'
    succs: List[int]              # sucessores estáticos (podem estar fora da imagem)
    next_addr: int                # endereço sequencial após a última instrução
    retaddr: bool = False         # começa na continuação de um JSR (alvo dinâmico de RTS)

    @property
    def end(self):
        return self.next_addr


@dataclass
class Cfg:
    org: int
    size: int
    entries: List[int]
    blocks: Dict[int, Block] = field(default_factory=dict)
    live_in: Dict[int, frozenset] = field(default_factory=dict)   # preenchido por cfg_liveness

    @property
    def starts(self) -> List[int]:
        return sorted(self.blocks)


def build_cfg(image: bytes, org: int, entries: Iterable[int]) -> Cfg:
    end = org + len(image)
    if end > 0x10000:
        raise ValueError("imagem ultrapassa o espaço de 64 KB")
    entries = sorted(set(entries))
    for e in entries:
        if not (org <= e < end):
            raise ValueError("entrada $%04X fora da imagem $%04X-$%04X" % (e, org, end - 1))

    inside = lambda a: org <= a < end
    insn_at: Dict[int, Insn] = {}
    owner: Dict[int, int] = {}           # byte -> endereço da instrução que o cobre
    leaders: Set[int] = set(entries)
    retconts: Set[int] = set()
    work = list(entries)

    while work:
        a = work.pop()
        while inside(a) and a not in insn_at:
            if a in owner:                       # cai NO MEIO de instrução já decodificada
                raise OverlapError(a, owner[a])
            insn = decode_one(image, a - org, a)
            for b in range(a, a + insn.length):
                if b in owner:
                    raise OverlapError(a, owner[b])
                owner[b] = a
            insn_at[a] = insn
            f = insn.flow
            if f == "seq":
                a = insn.next_addr
                continue
            if f == "branch":
                for t in (insn.target, insn.next_addr):
                    if inside(t):
                        leaders.add(t)
                        work.append(t)
            elif f == "jump":
                if inside(insn.target):
                    leaders.add(insn.target)
                    work.append(insn.target)
            elif f == "call":
                if inside(insn.target):
                    leaders.add(insn.target)
                    work.append(insn.target)
                n = insn.next_addr
                if inside(n):
                    leaders.add(n)
                    retconts.add(n)
                    work.append(n)
            break  # jump_ind, ret, e todos os acima terminam a varredura linear

    cfg = Cfg(org, len(image), entries)
    for start in sorted(leaders):
        insns: List[Insn] = []
        a = start
        while True:
            insn = insn_at[a]
            insns.append(insn)
            if insn.flow != "seq":
                kind = insn.flow
                break
            n = insn.next_addr
            if n in leaders or not inside(n):
                kind = "fall"
                break
            a = n
        last = insns[-1]
        if kind == "fall":
            succs = [last.next_addr]
        elif kind == "branch":
            succs = [last.target, last.next_addr]
        elif kind == "jump":
            succs = [last.target]
        elif kind == "call":
            succs = [last.target, last.next_addr]
        else:
            succs = []
        cfg.blocks[start] = Block(start, insns, kind, succs, last.next_addr, start in retconts)
    return cfg
