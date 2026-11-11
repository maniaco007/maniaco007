"""Pipeline decode -> CFG -> lift -> vivacidade -> (emit): ponto único usado pela CLI e pelos testes."""

from typing import Dict, Iterable, List, Tuple

from .cfg import Cfg, build_cfg
from .ir import IrOp
from .lift import lift
from .opt import cfg_liveness


def analyze(image: bytes, org: int, entries: Iterable[int], precise_exits: bool = False
            ) -> Tuple[Cfg, Dict[int, List[IrOp]]]:
    cfg = build_cfg(image, org, entries)
    ops = {s: lift(cfg.blocks[s].insns) for s in cfg.starts}
    cfg_liveness(cfg, ops, precise_exits)
    return cfg, ops
