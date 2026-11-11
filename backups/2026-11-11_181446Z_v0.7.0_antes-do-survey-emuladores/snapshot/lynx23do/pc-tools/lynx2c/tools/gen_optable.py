"""Gera lynx2c/optable.json (arquivo de dados de registro) a partir de listas EXPLÍCITAS de opcodes.

Os opcodes são digitados aqui (não derivados do padrão de bits) de propósito: o núcleo de referência
(lynxtrace/core65c02.py) os DERIVA por padrão aaabbbcc, e test_decode.py compara as duas fontes.
Uso: python3 pc-tools/lynx2c/tools/gen_optable.py   (sobrescreve optable.json)
"""
import json
import os

N, Z, C, V = "N", "Z", "C", "V"

# ---- opcodes por mnemônico: {modo: opcode} --------------------------------------------------------
OPS = {
    # grupo 1 (9 modos; "izp" = (zp), só 65C02)
    "LDA": dict(imm=0xA9, zp=0xA5, zpx=0xB5, abs=0xAD, absx=0xBD, absy=0xB9, izx=0xA1, izy=0xB1, izp=0xB2),
    "STA": dict(zp=0x85, zpx=0x95, abs=0x8D, absx=0x9D, absy=0x99, izx=0x81, izy=0x91, izp=0x92),
    "ADC": dict(imm=0x69, zp=0x65, zpx=0x75, abs=0x6D, absx=0x7D, absy=0x79, izx=0x61, izy=0x71, izp=0x72),
    "SBC": dict(imm=0xE9, zp=0xE5, zpx=0xF5, abs=0xED, absx=0xFD, absy=0xF9, izx=0xE1, izy=0xF1, izp=0xF2),
    "ORA": dict(imm=0x09, zp=0x05, zpx=0x15, abs=0x0D, absx=0x1D, absy=0x19, izx=0x01, izy=0x11, izp=0x12),
    "AND": dict(imm=0x29, zp=0x25, zpx=0x35, abs=0x2D, absx=0x3D, absy=0x39, izx=0x21, izy=0x31, izp=0x32),
    "EOR": dict(imm=0x49, zp=0x45, zpx=0x55, abs=0x4D, absx=0x5D, absy=0x59, izx=0x41, izy=0x51, izp=0x52),
    "CMP": dict(imm=0xC9, zp=0xC5, zpx=0xD5, abs=0xCD, absx=0xDD, absy=0xD9, izx=0xC1, izy=0xD1, izp=0xD2),
    "BIT": dict(imm=0x89, zp=0x24, zpx=0x34, abs=0x2C, absx=0x3C),
    # registradores X / Y e zero
    "LDX": dict(imm=0xA2, zp=0xA6, zpy=0xB6, abs=0xAE, absy=0xBE),
    "LDY": dict(imm=0xA0, zp=0xA4, zpx=0xB4, abs=0xAC, absx=0xBC),
    "STX": dict(zp=0x86, zpy=0x96, abs=0x8E),
    "STY": dict(zp=0x84, zpx=0x94, abs=0x8C),
    "STZ": dict(zp=0x64, zpx=0x74, abs=0x9C, absx=0x9E),
    "CPX": dict(imm=0xE0, zp=0xE4, abs=0xEC),
    "CPY": dict(imm=0xC0, zp=0xC4, abs=0xCC),
    # leitura-modificação-escrita e acumulador
    "INC": dict(acc=0x1A, zp=0xE6, zpx=0xF6, abs=0xEE, absx=0xFE),
    "DEC": dict(acc=0x3A, zp=0xC6, zpx=0xD6, abs=0xCE, absx=0xDE),
    "ASL": dict(acc=0x0A, zp=0x06, zpx=0x16, abs=0x0E, absx=0x1E),
    "LSR": dict(acc=0x4A, zp=0x46, zpx=0x56, abs=0x4E, absx=0x5E),
    "ROL": dict(acc=0x2A, zp=0x26, zpx=0x36, abs=0x2E, absx=0x3E),
    "ROR": dict(acc=0x6A, zp=0x66, zpx=0x76, abs=0x6E, absx=0x7E),
    "TSB": dict(zp=0x04, abs=0x0C),
    "TRB": dict(zp=0x14, abs=0x1C),
}
IMPLIED = dict(INX=0xE8, INY=0xC8, DEX=0xCA, DEY=0x88, TAX=0xAA, TXA=0x8A, TAY=0xA8, TYA=0x98,
               TSX=0xBA, TXS=0x9A, CLC=0x18, SEC=0x38, CLI=0x58, SEI=0x78, CLV=0xB8, CLD=0xD8, SED=0xF8,
               NOP=0xEA, PHA=0x48, PLA=0x68, PHX=0xDA, PLX=0xFA, PHY=0x5A, PLY=0x7A, PHP=0x08, PLP=0x28)
BRANCHES = dict(BPL=(0x10, N), BMI=(0x30, N), BVC=(0x50, V), BVS=(0x70, V),
                BCC=(0x90, C), BCS=(0xB0, C), BNE=(0xD0, Z), BEQ=(0xF0, Z))

# ---- ciclos 65C02 ([VERIFY] contra a doc do CPU do Lynx) ---------------------------------------------
RD = dict(imm=2, zp=3, zpx=4, zpy=4, abs=4, absx=4, absy=4, izx=6, izy=5, izp=5)
WR = dict(zp=3, zpx=4, zpy=4, abs=4, absx=5, absy=5, izx=6, izy=6, izp=5)
INCDEC = dict(acc=2, zp=5, zpx=6, abs=6, absx=7)                       # abs,X fixo em 7
SHIFT = dict(acc=2, zp=5, zpx=6, abs=6, absx=6)                        # abs,X: 6 + 1 se cruza página
TSBR = dict(zp=5, abs=6)
STORES = {"STA", "STX", "STY", "STZ"}
PC_READ_MODES = {"absx", "absy", "izy"}


def cycles_and_pc(mn, mode):
    if mn in STORES:
        return WR[mode], False
    if mn in ("INC", "DEC"):
        return INCDEC[mode], False
    if mn in ("ASL", "LSR", "ROL", "ROR"):
        return SHIFT[mode], mode == "absx"
    if mn in ("TSB", "TRB"):
        return TSBR[mode], False
    if mn in ("CPX", "CPY"):
        return RD[mode], False
    return RD[mode], mode in PC_READ_MODES


# ---- semântica de flags: defs / uses --------------------------------------------------------------
NZ = [N, Z]
SEM = {  # sem -> (defs, uses)
    "lda": (NZ, []), "ldx": (NZ, []), "ldy": (NZ, []),
    "sta": ([], []), "stx": ([], []), "sty": ([], []), "stz": ([], []),
    "adc": ([N, Z, C, V], [C, "D"]), "sbc": ([N, Z, C, V], [C, "D"]),
    "ora": (NZ, []), "and": (NZ, []), "eor": (NZ, []),
    "cmp": ([N, Z, C], []), "cpx": ([N, Z, C], []), "cpy": ([N, Z, C], []),
    "bit": ([N, Z, V], []), "bit_imm": ([Z], []),
    "inc": (NZ, []), "dec": (NZ, []),
    "asl": ([N, Z, C], []), "lsr": ([N, Z, C], []),
    "rol": ([N, Z, C], [C]), "ror": ([N, Z, C], [C]),
    "tsb": ([Z], []), "trb": ([Z], []),
    "inx": (NZ, []), "iny": (NZ, []), "dex": (NZ, []), "dey": (NZ, []),
    "tax": (NZ, []), "txa": (NZ, []), "tay": (NZ, []), "tya": (NZ, []), "tsx": (NZ, []), "txs": ([], []),
    "clc": ([C], []), "sec": ([C], []), "clv": ([V], []),
    "cli": ([], []), "sei": ([], []), "cld": ([], []), "sed": ([], []), "nop": ([], []),
    "pha": ([], []), "phx": ([], []), "phy": ([], []), "php": ([], [N, Z, C, V]),
    "pla": (NZ, []), "plx": (NZ, []), "ply": (NZ, []), "plp": ([N, Z, C, V], []),
    "brk": ([], [N, Z, C, V]), "rti": ([N, Z, C, V], []),
    "bra": ([], []), "jmp": ([], []), "jmp_ind": ([], []), "jmp_iax": ([], []), "jsr": ([], []), "rts": ([], []),
}
for mn, (op, f) in BRANCHES.items():
    SEM[mn.lower()] = ([], [f])

MODES = dict(imm=2, zp=2, zpx=2, zpy=2, abs=3, absx=3, absy=3, izx=2, izy=2, izp=2,
             rel=2, ind=3, iax=3, imp=1, acc=1, brk=2)


def build():
    ops = []

    def add(opc, mn, mode, cycles, pc, sem, flow="seq"):
        ops.append({"opcode": "0x%02X" % opc, "mnemonic": mn, "mode": mode, "cycles": cycles,
                    "page_cross": pc, "sem": sem, "flow": flow})

    for mn, tab in OPS.items():
        for mode, opc in tab.items():
            cyc, pc = cycles_and_pc(mn, mode)
            sem = mn.lower()
            if mn == "BIT" and mode == "imm":
                sem = "bit_imm"
            add(opc, mn, mode, cyc, pc, sem)
    for mn, opc in IMPLIED.items():
        cyc = 3 if mn in ("PHA", "PHX", "PHY", "PHP") else 4 if mn in ("PLA", "PLX", "PLY", "PLP") else 2
        add(opc, mn, "imp", cyc, False, mn.lower())
    for mn, (opc, f) in BRANCHES.items():
        add(opc, mn, "rel", 2, False, mn.lower(), "branch")
    add(0x80, "BRA", "rel", 2, False, "bra", "jump")
    add(0x4C, "JMP", "abs", 3, False, "jmp", "jump")
    add(0x6C, "JMP", "ind", 6, False, "jmp_ind", "jump_ind")
    add(0x7C, "JMP", "iax", 6, False, "jmp_iax", "jump_ind")
    add(0x20, "JSR", "abs", 6, False, "jsr", "call")
    add(0x60, "RTS", "imp", 6, False, "rts", "ret")
    add(0x00, "BRK", "brk", 7, False, "brk", "brk")
    add(0x40, "RTI", "imp", 6, False, "rti", "ret")
    ops.sort(key=lambda e: int(e["opcode"], 16))
    assert len({e["opcode"] for e in ops}) == len(ops), "opcode duplicado"
    for e in ops:
        assert e["sem"] in SEM, e
    return ops


def main():
    ops = build()
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lynx2c", "optable.json")
    nota = ("Ciclos: 65C02 padrao; ADC/SBC +1 em modo decimal (dinamico); +1 em cruzamento de pagina nas leituras "
            "abs,X / abs,Y / (zp),Y e nos shifts abs,X (INC/DEC abs,X fixo em 7); desvios: 2 +1 tomado +1 se cruzar "
            "pagina (estatico). JMP (abs) = 6 ciclos SEM o bug de wrap de pagina do NMOS. BRK=7 (2 bytes: o "
            "segundo e assinatura), RTI=6. [VERIFY] todos os ciclos contra a doc do CPU do Lynx.")
    with open(here, "w", encoding="utf-8") as f:
        f.write('{\n "version": 3,\n "cpu": %s,\n "nota": %s,\n "modes": %s,\n "sems": %s,\n "ops": [\n' % (
            json.dumps("65C02 (conjunto de uso comum; sem BBR/BBS/RMB/SMB/WAI/STP)", ensure_ascii=False),
            json.dumps(nota, ensure_ascii=False),
            json.dumps({k: {"bytes": v} for k, v in MODES.items()}),
            json.dumps({k: {"defs": d, "uses": u} for k, (d, u) in SEM.items()})))
        f.write(",\n".join("  " + json.dumps(e) for e in ops))
        f.write("\n ]\n}\n")
    print(len(ops), "opcodes ->", os.path.normpath(here))


if __name__ == "__main__":
    main()
