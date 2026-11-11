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
    undoc: bool = False  # opcode que o hardware executa mas o 65C02 não documenta (NOPs): vira aviso no CFG


MODELS = ("core", "lynx1", "lynx2")


class Optable:
    """Tabela de opcodes por MODELO de CPU (docs/12 §2):
      core  = os 178 opcodes documentados do 65C02 (estrito: qualquer outro é erro explícito);
      lynx1 = core + NOPs indocumentados (x3/xB/x7/xF e os de 2/3 bytes): 256 opcodes, nenhum indefinido;
      lynx2 = core + NOPs (x3/xB e multi-byte) + Rockwell RMBn/SMBn/BBRn/BBSn nos x7/xF: 256 opcodes."""

    def __init__(self, model="core", path=_PATH):
        if model not in MODELS:
            raise ValueError("modelo de CPU desconhecido: %r (use %s)" % (model, "/".join(MODELS)))
        self.model = model
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.modes = {k: v["bytes"] for k, v in raw["modes"].items()}
        self.sems = {k: (frozenset(v["defs"]), frozenset(v["uses"])) for k, v in raw["sems"].items()}
        self.by_opcode = {}
        entries = list(raw["ops"])
        if model != "core":
            entries += [e for e in raw.get("ext", []) if model in e["models"]]
        for e in entries:
            opc = int(e["opcode"], 16)
            if opc in self.by_opcode:
                raise ValueError("opcode duplicado na tabela: $%02X" % opc)
            if e["mode"] not in self.modes:
                raise ValueError("modo desconhecido: %s" % e["mode"])
            if e["sem"] not in self.sems:
                raise ValueError("semântica desconhecida: %s" % e["sem"])
            self.by_opcode[opc] = OpInfo(opc, e["mnemonic"], e["mode"], self.modes[e["mode"]],
                                         e["cycles"], bool(e["page_cross"]), e["sem"],
                                         e.get("flow", "seq"), bool(e.get("undoc", False)))

    def get(self, opcode):
        return self.by_opcode.get(opcode)

    def defs_uses(self, sem):
        return self.sems[sem]
