"""IR mínima: uma operação por instrução, com defs/uses de flags explícitos e região do operando."""

from dataclasses import dataclass, field
from typing import FrozenSet

REGION_RAM, REGION_SUZY, REGION_MIKEY, REGION_ROMVEC, REGION_DYNAMIC = (
    "RAM", "SUZY", "MIKEY", "ROMVEC", "DYNAMIC")


def region_of(addr: int) -> str:
    """Espelha lx_region_of() de lx_mem.h (manter sincronizado)."""
    if addr < 0xFC00:
        return REGION_RAM
    if addr <= 0xFCFF:
        return REGION_SUZY
    if addr <= 0xFDFF:
        return REGION_MIKEY
    return REGION_ROMVEC


@dataclass
class IrOp:
    insn: object                       # lynx2c.decode.Insn
    sem: str                           # lda | sta | adc | sbc
    defs: FrozenSet[str]               # flags que a operação define (subconjunto de NZCV)
    uses: FrozenSet[str]               # flags lidos (C, D)
    region: str                        # região do operando absoluto; DYNAMIC se indexado/indireto; RAM p/ ZP/imm
    dead: FrozenSet[str] = field(default_factory=frozenset)  # defs que a análise provou mortos

    @property
    def live_defs(self):
        return self.defs - self.dead
