"""Montador 65C02 mínimo, dirigido pela MESMA tabela de opcodes do tradutor (optable.json).

Serve para escrever programas de teste/demonstração (games/demo_bars). Itens:
  ("L", nome)                    rótulo
  ("DB", bytes|lista)            dados
  (mnemônico, modo[, operando])  instrução; operando = inteiro ou nome de rótulo; modos: imm zp zpx zpy abs absx absy
                                 izx izy izp ind iax rel acc imp (sem operando: acc/imp)
  Lynx II: ("RMB3","zp",zp) ("SMB3","zp",zp) e ("BBR3","zprel",zp,alvo) ("BBS3","zprel",zp,alvo)
  NOPs indocumentados: use ("DB", [opcode...]) — não têm mnemônico único.
"""
from .optable import Optable

_T = Optable()
_OPC = {(i.mnemonic, i.mode): i.opcode for i in _T.by_opcode.values()}
_LEN = {i.mode: i.length for i in _T.by_opcode.values()}
for _i in Optable(model="lynx2").by_opcode.values():            # Rockwell (mnemônico próprio por bit)
    if _i.mnemonic[:3] in ("RMB", "SMB", "BBR", "BBS"):
        _OPC[(_i.mnemonic, _i.mode)] = _i.opcode
        _LEN[_i.mode] = _i.length


def assemble(org, items):
    labels, addr = {}, org
    for it in items:                                           # passo 1: endereços
        if it[0] == "L":
            labels[it[1]] = addr
        elif it[0] == "DB":
            addr += len(bytes(it[1]))
        else:
            addr += _LEN[it[1]]
    out, addr = bytearray(), org
    for it in items:                                           # passo 2: bytes
        if it[0] == "L":
            continue
        if it[0] == "DB":
            out += bytes(it[1])
            addr += len(bytes(it[1]))
            continue
        mn, mode = it[0], it[1]
        op = it[2] if len(it) > 2 else None
        if isinstance(op, str):
            op = labels[op]
        if mode == "zprel":                                    # BBRn/BBSn zp,alvo
            tgt = it[3]
            tgt = labels[tgt] if isinstance(tgt, str) else tgt
            off = tgt - (addr + 3)
            if not -128 <= off <= 127:
                raise ValueError("desvio fora de alcance em $%04X (%d)" % (addr, off))
            out += bytes([_OPC[(mn, mode)], op & 0xFF, off & 0xFF])
            addr += 3
            continue
        if (mn, mode) not in _OPC:
            raise ValueError("combinação inexistente: %s %s" % (mn, mode))
        n = _LEN[mode]
        nxt = addr + n
        if mode == "rel":
            off = op - nxt
            if not -128 <= off <= 127:
                raise ValueError("desvio fora de alcance em $%04X (%d)" % (addr, off))
            op = off & 0xFF
        out.append(_OPC[(mn, mode)])
        if n == 2:
            out.append(op & 0xFF)
        elif n == 3:
            out += bytes([op & 0xFF, (op >> 8) & 0xFF])
        addr = nxt
    return bytes(out), labels
