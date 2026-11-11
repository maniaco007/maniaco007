"""Estágio D (parcial): Insn -> IrOp. Dirigido pela tabela (defs/uses vêm do optable.json)."""

from typing import Iterable, List

from .ir import IrOp, region_of, REGION_DYNAMIC, REGION_RAM
from .optable import Optable

_TABLE = Optable()


def lift(insns: Iterable) -> List[IrOp]:
    ops = []
    for insn in insns:
        defs, uses = _TABLE.defs_uses(insn.sem)
        if insn.mode == "abs":
            region = region_of(insn.operand)      # operando absoluto: região estática
        elif insn.mode in ("imm", "zp", "zpx"):
            region = REGION_RAM                     # imediato / zero page: sempre RAM
        else:
            region = REGION_DYNAMIC                 # indexado/indireto: depende de registradores/RAM
        ops.append(IrOp(insn, insn.sem, defs, uses, region))
    return ops
