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
    página e +1 do modo decimal são somados dinamicamente;
  - FLUXO DE CONTROLE (fase 1, trampolim): um bloco termina em desvio/salto/JSR/RTS ou ao cair
    num líder; a função RETORNA o próximo PC (lx_run despacha pela tabela do overlay).
    JSR empilha (endereço do último byte do JSR) e RTS desempilha +1, na pilha EMULADA
    ($0100-$01FF), então "RTS trick" e troca de pilha funcionam sem tratamento especial.
    Desvio tomado soma +1 ciclo (+1 se o alvo cruza página, decidido na tradução).
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
#include "lynx/lx_overlay.h"

#if LX_ABI_VERSION != %(abi)d
#error "ABI do runtime diverge da usada pelo lynx2c: regenerar o código"
#endif
"""


class _Ctx:
    def __init__(self):
        self.ea = self.m = self.t = self.pc = False


_BRANCH_COND = {
    "bpl": "!(cpu->nsrc & 0x80)", "bmi": "(cpu->nsrc & 0x80)",
    "bvc": "!cpu->v", "bvs": "cpu->v",
    "bcc": "!cpu->c", "bcs": "cpu->c",
    "bne": "(cpu->zsrc != 0)", "beq": "(cpu->zsrc == 0)",
}


def _taken_extra(insn) -> int:
    """Ciclos extras de um desvio tomado: +1, e +1 se alvo e instrução seguinte estão em páginas diferentes."""
    return 1 + (1 if ((insn.target ^ insn.next_addr) & 0xFF00) else 0)


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
    elif insn.flow != "seq":
        L += _emit_terminator(op, ctx)
    else:
        raise AssertionError("semântica não suportada: %s" % op.sem)
    return L


def _emit_terminator(op: IrOp, ctx: _Ctx) -> List[str]:
    """Linhas que deixam o PC de destino na variável local 'pc'."""
    insn = op.insn
    ctx.pc = True
    sem = op.sem
    if sem in _BRANCH_COND:
        return ["if (%s) {" % _BRANCH_COND[sem],
                "    cpu->cycles += %d;" % _taken_extra(insn),
                "    pc = 0x%04X;" % insn.target,
                "} else {",
                "    pc = 0x%04X;" % insn.next_addr,
                "}"]
    if sem == "bra":
        return ["cpu->cycles += %d;" % _taken_extra(insn), "pc = 0x%04X;" % insn.target]
    if sem == "jmp":
        return ["pc = 0x%04X;" % insn.target]
    if sem == "jmp_ind":
        return ["pc = lx_rd16(0x%04X);   /* 65C02: sem o bug de wrap de página do NMOS */" % insn.operand]
    if sem == "jmp_iax":
        ctx.ea = True
        return ["ea = (0x%04X + cpu->x) & 0xFFFF;" % insn.operand, "pc = lx_rd16(ea);"]
    if sem == "jsr":
        ret = (insn.addr + 2) & 0xFFFF          # endereço do ÚLTIMO byte do JSR (RTS soma 1)
        return ["lx_push8(&cpu->s, 0x%02X);" % (ret >> 8), "lx_push8(&cpu->s, 0x%02X);" % (ret & 0xFF),
                "pc = 0x%04X;" % insn.target]
    if sem == "rts":
        ctx.t = True
        return ["t = lx_pull8(&cpu->s);", "t |= (lx_u32)lx_pull8(&cpu->s) << 8;", "pc = (t + 1) & 0xFFFF;"]
    raise AssertionError("terminador não suportado: %s" % sem)


def emit_block(name: str, ops: Sequence[IrOp], org: int) -> str:
    """Emite UMA função C para um bloco reto que começa em 'org' e cai no PC seguinte."""
    if not ops:
        raise ValueError("bloco vazio")
    ctx = _Ctx()
    body: List[str] = []
    for i, op in enumerate(ops):
        if op.insn.flow != "seq" and i != len(ops) - 1:
            raise ValueError("instrução de fluxo no meio do bloco em $%04X" % op.insn.addr)
        body += _emit_op(op, ctx)
    terminated = ops[-1].insn.flow != "seq"
    next_pc = ops[-1].insn.next_addr
    total = sum(op.insn.cycles for op in ops)

    decls = []
    if ctx.ea:
        decls.append("lx_u32 ea;")
    if ctx.m:
        decls.append("lx_u32 m;")
    if ctx.t:
        decls.append("lx_u32 t;")
    if ctx.pc:
        decls.append("lx_u32 pc;")

    out = ["/* bloco $%04X..$%04X, %d instrução(ões), %d ciclos base */" %
           (org, (next_pc - 1) & 0xFFFF, len(ops), total),
           "lx_u32 %s(LxCpu *cpu)" % name, "{"]
    out += ["    " + d for d in decls]
    if decls:
        out.append("")
    out += ["    " + l for l in body]
    out.append("")
    if terminated:
        out.append("    LX_SCHED_CHECK(cpu, %d, pc);" % total)
        out.append("    return pc;")
    else:
        out.append("    LX_SCHED_CHECK(cpu, %d, 0x%04X);" % (total, next_pc))
        out.append("    return 0x%04X;" % next_pc)
    out.append("}")
    return "\n".join(out) + "\n"


def block_fn_name(overlay_id: int, start: int) -> str:
    return "lx_ov%d_%04X" % (overlay_id, start)


def emit_overlay(overlay_id: int, cfg, ops_by_block, cart_offset: int = 0) -> str:
    """Emite funções de TODOS os blocos de um CFG + tabela de despacho + descritor LxOverlay.
    Fase 1: todo bloco entra na tabela (o trampolim despacha por PC). Fase 2 reduzirá a tabela
    aos alvos dinâmicos (docs/02 §7)."""
    parts = []
    for start in cfg.starts:
        parts.append(emit_block(block_fn_name(overlay_id, start), ops_by_block[start], start))
    rows = []
    for start in cfg.starts:
        flags = "LX_DE_RETADDR" if cfg.blocks[start].retaddr else "0"
        rows.append("    { 0x%04X, %s, %s }" % (start, flags, block_fn_name(overlay_id, start)))
    parts.append("static const LxDispatchEntry lx_ov%d_entries[] = {\n%s\n};\n" %
                 (overlay_id, ",\n".join(rows)))
    parts.append("const LxOverlay lx_ov%d = {\n"
                 "    %d, 0x%04X, 0x%04X, %d, 0x%X, 0, lx_ov%d_entries\n};\n" %
                 (overlay_id, overlay_id, cfg.org, cfg.size, len(cfg.starts), cart_offset, overlay_id))
    return "\n".join(parts)


def emit_unit(blocks: Iterable[Tuple[str, Sequence[IrOp], int]]) -> str:
    """Emite um arquivo .c completo com vários blocos: [(nome, ops, org), ...]."""
    parts = [_HEADER % {"ver": __version__, "abi": ABI_VERSION}]
    for name, ops, org in blocks:
        parts.append(emit_block(name, ops, org))
    return "\n".join(parts)
