"""Pipeline decode -> CFG -> lift -> vivacidade -> (emit): ponto único usado pela CLI e pelos testes."""

from typing import Dict, Iterable, List, Tuple

from .cfg import Cfg, build_cfg
from .ir import IrOp
from .lift import lift
from .opt import cfg_liveness
from .optable import Optable


def analyze(image: bytes, org: int, entries: Iterable[int], precise_exits: bool = False,
            smc_operands: Iterable[int] = (), hooks: Iterable[int] = (),
            cpu: str = "lynx1") -> Tuple[Cfg, Dict[int, List[IrOp]]]:
    """cpu: modelo de CPU — 'lynx1' (padrão), 'lynx2' (Rockwell) ou 'core' (estrito: só os 178 documentados)."""
    cfg = build_cfg(image, org, entries, smc_operands, hooks, Optable(model=cpu))
    ops = {s: lift(cfg.blocks[s].insns) for s in cfg.starts}
    cfg_liveness(cfg, ops, precise_exits)
    return cfg, ops
