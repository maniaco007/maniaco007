"""Medição do tamanho REAL do código gerado, compilado para ARM big-endian (o ARM60 do 3DO é BE).

Usa o clang como compilador cruzado (--target=armeb-none-eabi, ARM7TDMI/ARMv4, modo ARM) e `llvm-size`.
Limites a ter em mente (documentados em docs/04):
  - ARMv4 (clang) e não ARMv3 (ARM60): o código gerado só usa acessos de byte e palavra, então a contagem de
    instruções é praticamente a mesma;
  - clang -Os costuma gerar código MENOR que o armcc 2.x do SDK 3DO: tratar o resultado como piso, não como teto;
  - mede o código da fase 1 (registradores em LxCpu); a fase 2 deve reduzi-lo.
Sem clang/llvm-size no PATH, devolve None (o relatório então usa o fator medido como estimativa, e diz isso).
"""
import os
import shutil
import subprocess
import tempfile
from typing import Optional

TARGET = ["--target=armeb-none-eabi", "-mcpu=arm7tdmi", "-marm"]


def available() -> bool:
    return bool(shutil.which("clang") and shutil.which("llvm-size"))


def measure_c(c_path: str, include_dir: str, opt: str = "-Os") -> Optional[dict]:
    """Compila 'c_path' (C89 gerado pelo lynx2c) para ARM BE e devolve tamanhos em bytes."""
    if not available():
        return None
    with tempfile.TemporaryDirectory() as td:
        obj = os.path.join(td, "o.o")
        cc = subprocess.run(["clang"] + TARGET + [opt, "-ffreestanding", "-std=c89", "-fno-pic", "-w",
                                                  "-I", include_dir, "-c", c_path, "-o", obj],
                            capture_output=True, text=True)
        if cc.returncode:
            raise RuntimeError("clang falhou ao compilar %s:\n%s" % (c_path, cc.stderr[:1500]))
        out = subprocess.run(["llvm-size", "-A", obj], capture_output=True, text=True, check=True).stdout
    text = ro = data = 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("."):
            name, size = parts[0], int(parts[1])
            if name.startswith(".text"):
                text += size
            elif name.startswith(".rodata") or name.startswith(".data.rel.ro"):
                ro += size
            elif name.startswith(".data"):
                data += size
    return {"text": text, "rodata": ro, "data": data, "total": text + ro + data, "opt": opt}
