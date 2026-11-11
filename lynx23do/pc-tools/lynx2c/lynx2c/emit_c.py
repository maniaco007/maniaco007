"""Estágio F (parcial): IR -> C89 (fase 1 do docs/02 §7: um bloco reto = uma função LxCodeFn).

Convenções do código gerado (contrato = runtime/include/lynx/lx_cpu_abi.h):
  - registradores A,X,Y,S e flags vivem em LxCpu (fase 1); fase 2 promoverá a locais ARM;
  - N/Z preguiçosos: cpu->nsrc / cpu->zsrc recebem o valor que originou o flag;
  - operando absoluto: região resolvida AQUI (RAM direto | lx_suzy_* | lx_mikey_* | lx_io_*);
  - operando indexado/indireto: lx_rd8()/lx_wr8() (1 comparação em runtime);
  - zero page SEMPRE em lx_ram com wrap de 8 bits; ponteiros ZP via lx_zp_ptr();
  - leitura de operando é feita EXATAMENTE uma vez e escrita EXATAMENTE uma vez
    (acessos a E/S têm efeito colateral);
  - ciclos: soma constante no fim do bloco (LX_SCHED_CHECK); +1 de cruzamento de
    página e +1 do modo decimal são somados dinamicamente.
"""

from typing import Iterable, List, Sequence, Tuple

from . import ABI_VERSION, __version__
from .ir import IrOp, region_of

_HEADER = """\
/* GERADO por lynx2c %(ver)s — NÃO EDITAR. Mudanças vão no tradutor/manifest.
 * ABI: LX_ABI_VERSION == %(abi)d (conferido em tempo de compilação). */
#include "lynx/lx_cpu_abi.h"
#include "lynx/lx_mem.h"
#include "lynx/lx_suzy.h"
#include "lynx/lx_mikey.h"
#include "lynx/lx_alu.h"

#if LX_ABI_VERSION != %(abi)d
#error "ABI do runtime diverge da usada pelo lynx2c: regenerar o código"
#endif
"""


class _Ctx:
    def __init__(self):
        self.ea = self.m = self.t = False


def _static_read(addr: int) -> str:
    r = region_of(addr)
    if r == "RAM":
        return "lx_ram[0x%04X]" % addr
    if r == "SUZY":
        return "lx_suzy_read(0x%04X)" % addr
    if r == "MIKEY":
        return "lx_mikey_read(0x%04X)" % addr
    return "lx_io_read(0x%04X)" % addr


def _static_write(addr: int, val: str) -> str:
    r = region_of(addr)
    if r == "RAM":
        return "lx_ram[0x%04X] = %s;" % (addr, val)
    if r == "SUZY":
        return "lx_suzy_write(0x%04X, %s);" % (addr, val)
    if r == "MIKEY":
        return "lx_mikey_write(0x%04X, %s);" % (addr, val)
    return "lx_io_write(0x%04X, %s);" % (addr, val)


def _ea_lines(insn, ctx: _Ctx, with_page_cross: bool) -> List[str]:
    """Calcula o endereço efetivo em 'ea' para modos não-estáticos (com wrap correto)."""
    mode, o = insn.mode, insn.operand
    ctx.ea = True
    if mode == "zpx":
        return ["ea = (0x%02X + cpu->x) & 0xFF;" % o]
    if mode in ("absx", "absy"):
        reg = "x" if mode == "absx" else "y"
        lines = ["ea = (0x%04X + cpu->%s) & 0xFFFF;" % (o, reg)]
        if with_page_cross:
            lines.append("if ((0x%02X + cpu->%s) > 0xFF) cpu->cycles += 1;" % (o & 0xFF, reg))
        return lines
    if mode == "izx":
        return ["ea = lx_zp_ptr((0x%02X + cpu->x) & 0xFF);" % o]
    if mode == "izy":
        lines = ["ea = lx_zp_ptr(0x%02X);" % o]
        if with_page_cross:
            lines.append("if (((ea & 0xFF) + cpu->y) > 0xFF) cpu->cycles += 1;")
        lines.append("ea = (ea + cpu->y) & 0xFFFF;")
        return lines
    if mode == "izp":
        return ["ea = lx_zp_ptr(0x%02X);" % o]
    raise AssertionError("modo sem EA: %s" % mode)


def _read_operand(insn, ctx: _Ctx) -> List[str]:
    """Gera linhas que deixam o byte do operando em 'm' (leitura única)."""
    ctx.m = True
    mode, o = insn.mode, insn.operand
    if mode == "imm":
        return ["m = 0x%02X;" % o]
    if mode == "zp":
        return ["m = lx_ram[0x%02X];" % o]
    if mode == "abs":
        return ["m = %s;" % _static_read(o)]
    if mode == "zpx":
        lines = _ea_lines(insn, ctx, insn.page_cross)
        return lines + ["m = lx_ram[ea];"]          # zp,X: ea já está em 0..255
    return _ea_lines(insn, ctx, insn.page_cross) + ["m = lx_rd8(ea);"]


def _write_operand(insn, val: str, ctx: _Ctx) -> List[str]:
    mode, o = insn.mode, insn.operand
    if mode == "zp":
        return ["lx_ram[0x%02X] = %s;" % (o, val)]
    if mode == "abs":
        return [_static_write(o, val)]
    if mode == "zpx":
        return _ea_lines(insn, ctx, False) + ["lx_ram[ea] = %s;" % val]
    return _ea_lines(insn, ctx, False) + ["lx_wr8(ea, %s);" % val]


def _set_nz(live, src: str) -> List[str]:
    out = []
    if "N" in live:
        out.append("cpu->nsrc = %s;" % src)
    if "Z" in live:
        out.append("cpu->zsrc = %s;" % src)
    return out


def _emit_op(op: IrOp, ctx: _Ctx) -> List[str]:
    insn, live = op.insn, op.live_defs
    L = ["/* $%04X  %s */" % (insn.addr, insn.text())]
    if op.sem == "lda":
        L += _read_operand(insn, ctx)
        L.append("cpu->a = (lx_u8)m;")
        L += _set_nz(live, "cpu->a")
    elif op.sem == "sta":
        L += _write_operand(insn, "cpu->a", ctx)
    elif op.sem in ("adc", "sbc"):
        ctx.t = True
        L += _read_operand(insn, ctx)
        dec = "lx_adc_dec" if op.sem == "adc" else "lx_sbc_dec"
        L.append("if (cpu->d) {")
        L.append("    %s(cpu, (lx_u8)m);   /* decimal: define todos os flags */" % dec)
        L.append("    cpu->cycles += 1;     /* 65C02: +1 ciclo em modo decimal */")
        L.append("} else {")
        if op.sem == "adc":
            L.append("    t = (lx_u32)cpu->a + m + cpu->c;")
            if "V" in live:
                L.append("    cpu->v = (lx_u8)(((~((lx_u32)cpu->a ^ m)) & ((lx_u32)cpu->a ^ t) & 0x80) != 0);")
        else:
            L.append("    t = (lx_u32)cpu->a + (m ^ 0xFF) + cpu->c;")
            if "V" in live:
                L.append("    cpu->v = (lx_u8)((((lx_u32)cpu->a ^ m) & ((lx_u32)cpu->a ^ t) & 0x80) != 0);")
        if "C" in live:
            L.append("    cpu->c = (lx_u8)(t > 0xFF);")
        L.append("    cpu->a = (lx_u8)t;")
        L += ["    " + s for s in _set_nz(live, "cpu->a")]
        L.append("}")
    else:
        raise AssertionError("semântica não suportada: %s" % op.sem)
    return L


def emit_block(name: str, ops: Sequence[IrOp], org: int) -> str:
    """Emite UMA função C para um bloco reto que começa em 'org' e cai no PC seguinte."""
    if not ops:
        raise ValueError("bloco vazio")
    ctx = _Ctx()
    body: List[str] = []
    for op in ops:
        body += _emit_op(op, ctx)
    next_pc = ops[-1].insn.next_addr
    total = sum(op.insn.cycles for op in ops)

    decls = []
    if ctx.ea:
        decls.append("lx_u32 ea;")
    if ctx.m:
        decls.append("lx_u32 m;")
    if ctx.t:
        decls.append("lx_u32 t;")

    out = ["/* bloco $%04X..$%04X, %d instrução(ões), %d ciclos base */" %
           (org, (next_pc - 1) & 0xFFFF, len(ops), total),
           "lx_u32 %s(LxCpu *cpu)" % name, "{"]
    out += ["    " + d for d in decls]
    if decls:
        out.append("")
    out += ["    " + l for l in body]
    out.append("")
    out.append("    LX_SCHED_CHECK(cpu, %d, 0x%04X);" % (total, next_pc))
    out.append("    return 0x%04X;" % next_pc)
    out.append("}")
    return "\n".join(out) + "\n"


def emit_unit(blocks: Iterable[Tuple[str, Sequence[IrOp], int]]) -> str:
    """Emite um arquivo .c completo com vários blocos: [(nome, ops, org), ...]."""
    parts = [_HEADER % {"ver": __version__, "abi": ABI_VERSION}]
    for name, ops, org in blocks:
        parts.append(emit_block(name, ops, org))
    return "\n".join(parts)
