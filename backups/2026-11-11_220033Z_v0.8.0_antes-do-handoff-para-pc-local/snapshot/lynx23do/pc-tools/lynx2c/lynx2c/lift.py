"""Estágio D (parcial): Insn -> IrOp. Dirigido pela tabela (defs/uses vêm do optable.json)."""

from typing import Iterable, List

from .ir import IrOp, region_of, REGION_DYNAMIC, REGION_RAM
from .optable import Optable

_TABLE = Optable("lynx2")     # só defs/uses por 'sem' (idênticos em todos os modelos): lynx2 é o superconjunto de semânticas


def lift(insns: Iterable) -> List[IrOp]:
    ops = []
    for insn in insns:
        defs, uses = _TABLE.defs_uses(insn.sem)
        if insn.flow in ("branch", "ret", "brk") or insn.mode in ("imp", "acc", "brk") or insn.flow in ("jump", "call"):
            region = "NONE"                         # alvo de salto/desvio: não é acesso a memória de dados
        elif insn.mode == "abs":
            region = region_of(insn.operand)      # operando absoluto: região estática
        elif insn.mode in ("nop1", "nop2", "nop3"):
            region = "NONE"                         # NOP: operando nunca é lido (docs/12 §2)
        elif insn.mode in ("imm", "zp", "zpx", "zpy"):
            region = REGION_RAM                     # imediato / zero page: sempre RAM
        else:
            region = REGION_DYNAMIC                 # indexado/indireto: depende de registradores/RAM
        ops.append(IrOp(insn, insn.sem, defs, uses, region))
    return ops
