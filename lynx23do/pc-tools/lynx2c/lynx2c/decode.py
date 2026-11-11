"""Decoder 65C02 (subconjunto). Nunca adivinha: opcode fora da tabela é erro explícito."""

from dataclasses import dataclass
from typing import List, Optional

from .optable import Optable

_TABLE = Optable("lynx1")      # padrão: Lynx I (todos os cartuchos comerciais); "core" = estrito, "lynx2" = com Rockwell


class DecodeError(Exception):
    pass


class UnsupportedOpcode(DecodeError):
    def __init__(self, opcode, addr):
        super().__init__("opcode $%02X em $%04X ainda não suportado pelo lynx2c" % (opcode, addr))
        self.opcode, self.addr = opcode, addr


class TruncatedInstruction(DecodeError):
    def __init__(self, addr):
        super().__init__("instrução em $%04X truncada (faltam bytes de operando)" % addr)
        self.addr = addr


@dataclass(frozen=True)
class Insn:
    addr: int
    opcode: int
    mnemonic: str
    mode: str
    length: int
    operand: Optional[int]  # None p/ modos sem operando (nenhum no subconjunto atual)
    cycles: int
    page_cross: bool
    sem: str
    flow: str = "seq"        # seq | branch | jump | jump_ind | call | ret | brk
    target: Optional[int] = None   # alvo ESTÁTICO (branch/BRA/JMP abs/JSR); None se dinâmico
    smc: bool = False              # operando modificado em execução (política param_operand): lido da RAM a cada vez
    undoc: bool = False            # NOP indocumentado (o hardware o executa; aviso no CFG — pode ser dado mal classificado)

    @property
    def next_addr(self):
        return (self.addr + self.length) & 0xFFFF

    def text(self):
        o, m = self.operand, self.mode
        if m in ("imp", "brk"):
            return self.mnemonic
        if m == "acc":
            return self.mnemonic + " A"
        if m == "rel":
            return "%s $%04X" % (self.mnemonic, self.target)
        if m == "zprel":
            return "%s $%02X,$%04X" % (self.mnemonic, o & 0xFF, self.target)
        if m == "nop1":
            return "NOP[%02X]" % self.opcode
        if m == "nop2":
            return "NOP[%02X] $%02X" % (self.opcode, o)
        if m == "nop3":
            return "NOP[%02X] $%04X" % (self.opcode, o)
        if m == "imm" and self.smc:
            return "%s #<SMC>" % self.mnemonic
        fmt = {"imm": "#$%02X", "zp": "$%02X", "zpx": "$%02X,X", "zpy": "$%02X,Y", "abs": "$%04X",
               "absx": "$%04X,X", "absy": "$%04X,Y", "izx": "($%02X,X)",
               "izy": "($%02X),Y", "izp": "($%02X)", "ind": "($%04X)", "iax": "($%04X,X)"}[m]
        return "%s %s" % (self.mnemonic, fmt % o)


def decode_one(data: bytes, offset: int, addr: int, table: Optable = _TABLE) -> Insn:
    opcode = data[offset]
    info = table.get(opcode)
    if info is None:
        raise UnsupportedOpcode(opcode, addr)
    if offset + info.length > len(data):
        raise TruncatedInstruction(addr)
    if info.length == 1:
        operand = None
    elif info.length == 2:
        operand = data[offset + 1]
    else:
        operand = data[offset + 1] | (data[offset + 2] << 8)  # little-endian, composto de bytes
    addr &= 0xFFFF
    target = None
    if info.mode == "rel":
        off = operand - 256 if operand & 0x80 else operand
        target = (addr + 2 + off) & 0xFFFF
    elif info.mode == "zprel":                 # BBRn/BBSn zp,rel: operando = zp | rel << 8 (3 bytes, alvo relativo ao fim)
        rel = operand >> 8
        off = rel - 256 if rel & 0x80 else rel
        target = (addr + 3 + off) & 0xFFFF
    elif info.flow in ("jump", "call") and info.mode == "abs":
        target = operand
    return Insn(addr, opcode, info.mnemonic, info.mode, info.length,
                operand, info.cycles, info.page_cross, info.sem, info.flow, target, undoc=info.undoc)


def decode_block(data: bytes, org: int, table: Optable = _TABLE) -> List[Insn]:
    """Decodifica linearmente TODO o buffer como UM bloco reto (sem fluxo de controle ainda)."""
    out, off = [], 0
    while off < len(data):
        insn = decode_one(data, off, org + off, table)
        out.append(insn)
        off += insn.length
    return out
