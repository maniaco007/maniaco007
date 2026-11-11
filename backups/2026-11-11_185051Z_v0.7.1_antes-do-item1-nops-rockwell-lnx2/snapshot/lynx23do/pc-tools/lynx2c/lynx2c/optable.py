"""Carrega e valida a tabela de opcodes (optable.json, arquivo de dados — decisão D1)."""

import json
import os
from dataclasses import dataclass

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "optable.json")
FLAGS = ("N", "Z", "C", "V")


@dataclass(frozen=True)
class OpInfo:
    opcode: int
    mnemonic: str
    mode: str
    length: int
    cycles: int
    page_cross: bool
    sem: str
    flow: str = "seq"   # seq | branch | jump | jump_ind | call | ret


class Optable:
    def __init__(self, path=_PATH):
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.modes = {k: v["bytes"] for k, v in raw["modes"].items()}
        self.sems = {k: (frozenset(v["defs"]), frozenset(v["uses"])) for k, v in raw["sems"].items()}
        self.by_opcode = {}
        for e in raw["ops"]:
            opc = int(e["opcode"], 16)
            if opc in self.by_opcode:
                raise ValueError("opcode duplicado na tabela: $%02X" % opc)
            if e["mode"] not in self.modes:
                raise ValueError("modo desconhecido: %s" % e["mode"])
            if e["sem"] not in self.sems:
                raise ValueError("semântica desconhecida: %s" % e["sem"])
            self.by_opcode[opc] = OpInfo(opc, e["mnemonic"], e["mode"], self.modes[e["mode"]],
                                         e["cycles"], bool(e["page_cross"]), e["sem"],
                                         e.get("flow", "seq"))

    def get(self, opcode):
        return self.by_opcode.get(opcode)

    def defs_uses(self, sem):
        return self.sems[sem]
