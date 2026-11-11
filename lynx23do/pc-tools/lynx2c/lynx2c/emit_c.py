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

import re
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
    if mode in ("zpx", "zpy"):
        return ["ea = (0x%02X + cpu->%s) & 0xFF;" % (o, "x" if mode == "zpx" else "y")]
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
        if insn.smc:                                  # param_operand: operando lido da RAM a cada execução
            return ["m = lx_rd8(0x%04X);   /* operando auto-modificável */" % ((insn.addr + 1) & 0xFFFF)]
        return ["m = 0x%02X;" % o]
    if mode == "zp":
        return ["m = lx_ram[0x%02X];" % o]
    if mode == "abs":
        return ["m = %s;" % _static_read(o)]
    if mode in ("zpx", "zpy"):
        lines = _ea_lines(insn, ctx, insn.page_cross)
        return lines + ["m = lx_ram[ea];"]          # zp,X / zp,Y: ea já está em 0..255
    return _ea_lines(insn, ctx, insn.page_cross) + ["m = lx_rd8(ea);"]


def _write_operand(insn, val: str, ctx: _Ctx) -> List[str]:
    mode, o = insn.mode, insn.operand
    if mode == "zp":
        return ["lx_ram[0x%02X] = %s;" % (o, val)]
    if mode == "abs":
        return [_static_write(o, val)]
    if mode in ("zpx", "zpy"):
        return _ea_lines(insn, ctx, False) + ["lx_ram[ea] = %s;" % val]
    return _ea_lines(insn, ctx, False) + ["lx_wr8(ea, %s);" % val]


def _store_after_read(insn, val: str) -> List[str]:
    """RMW: escreve 'val' no MESMO endereço já lido (o 'ea' dos modos dinâmicos já foi calculado)."""
    mode, o = insn.mode, insn.operand
    if mode == "zp":
        return ["lx_ram[0x%02X] = %s;" % (o, val)]
    if mode == "abs":
        return [_static_write(o, val)]
    if mode in ("zpx", "zpy"):
        return ["lx_ram[ea] = %s;" % val]
    return ["lx_wr8(ea, %s);" % val]


_REG = {"lda": "a", "ldx": "x", "ldy": "y", "sta": "a", "stx": "x", "sty": "y",
        "cmp": "a", "cpx": "x", "cpy": "y"}
_TRANSFER = {"tax": ("x", "a"), "tay": ("y", "a"), "txa": ("a", "x"), "tya": ("a", "y"),
             "tsx": ("x", "s"), "txs": ("s", "x")}
_FLAGSET = {"clc": "cpu->c = 0;", "sec": "cpu->c = 1;", "clv": "cpu->v = 0;",
            "cld": "cpu->d = 0;", "sed": "cpu->d = 1;", "cli": "cpu->i = 0;", "sei": "cpu->i = 1;"}


def _emit_rmw(op: IrOp, ctx: _Ctx) -> List[str]:
    """INC DEC ASL LSR ROL ROR (acumulador ou memória): leitura única, escrita única."""
    insn, live, sem = op.insn, op.live_defs, op.sem
    ctx.t = ctx.m = True
    L = ["m = cpu->a;"] if insn.mode == "acc" else _read_operand(insn, ctx)
    carry = None
    if sem == "inc":
        L.append("t = (m + 1) & 0xFF;")
    elif sem == "dec":
        L.append("t = (m - 1) & 0xFF;")
    elif sem == "asl":
        L.append("t = (m << 1) & 0xFF;")
        carry = "(m >> 7) & 1"
    elif sem == "lsr":
        L.append("t = m >> 1;")
        carry = "m & 1"
    elif sem == "rol":
        L.append("t = ((m << 1) | cpu->c) & 0xFF;")      # usa o C ANTIGO: calcular t antes de atualizar C
        carry = "(m >> 7) & 1"
    else:  # ror
        L.append("t = (m >> 1) | ((lx_u32)cpu->c << 7);")
        carry = "m & 1"
    if carry and "C" in live:
        L.append("cpu->c = (lx_u8)(%s);" % carry)
    if sem == "lsr":                                       # N = 0 sempre
        if "N" in live:
            L.append("cpu->nsrc = 0;")
        if "Z" in live:
            L.append("cpu->zsrc = (lx_u8)t;")
    else:
        L += _set_nz(live, "(lx_u8)t")
    if insn.mode == "acc":
        L.append("cpu->a = (lx_u8)t;")
    else:
        L += _store_after_read(insn, "(lx_u8)t")
    return L


def _emit_implied(op: IrOp, ctx: _Ctx) -> List[str]:
    sem, live = op.sem, op.live_defs
    if sem in ("inx", "iny", "dex", "dey"):
        reg = sem[2]
        return ["cpu->%s = (lx_u8)(cpu->%s %s 1);" % (reg, reg, "+" if sem[1] == "n" else "-")] + \
            _set_nz(live, "cpu->%s" % reg)
    if sem in _TRANSFER:
        dst, src = _TRANSFER[sem]
        return ["cpu->%s = cpu->%s;" % (dst, src)] + _set_nz(live, "cpu->%s" % dst)
    if sem in _FLAGSET:
        return [_FLAGSET[sem]]
    if sem == "nop":
        return []
    if sem in ("pha", "phx", "phy"):
        return ["lx_push8(&cpu->s, cpu->%s);" % {"pha": "a", "phx": "x", "phy": "y"}[sem]]
    if sem == "php":
        return ["lx_push8(&cpu->s, (lx_u8)(lx_cpu_pack_p(cpu) | 0x10));   /* B=1 no P empilhado */"]
    if sem in ("pla", "plx", "ply"):
        reg = {"pla": "a", "plx": "x", "ply": "y"}[sem]
        return ["cpu->%s = lx_pull8(&cpu->s);" % reg] + _set_nz(live, "cpu->%s" % reg)
    if sem == "plp":
        return ["lx_cpu_unpack_p(cpu, lx_pull8(&cpu->s));", "cpu->b = 0;   /* PLP/RTI ignoram o bit B */"]
    raise AssertionError("implícita não suportada: %s" % sem)


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
    elif op.sem in ("lda", "ldx", "ldy"):
        L += _read_operand(insn, ctx)
        L.append("cpu->%s = (lx_u8)m;" % _REG[op.sem])
        L += _set_nz(live, "cpu->%s" % _REG[op.sem])
    elif op.sem in ("sta", "stx", "sty"):
        L += _write_operand(insn, "cpu->%s" % _REG[op.sem], ctx)
    elif op.sem == "stz":
        L += _write_operand(insn, "0", ctx)
    elif op.sem in ("ora", "and", "eor"):
        L += _read_operand(insn, ctx)
        L.append("cpu->a = (lx_u8)(cpu->a %s m);" % {"ora": "|", "and": "&", "eor": "^"}[op.sem])
        L += _set_nz(live, "cpu->a")
    elif op.sem in ("cmp", "cpx", "cpy"):
        reg = _REG[op.sem]
        L += _read_operand(insn, ctx)
        if not live:
            L.append("(void)m;")                         # leitura mantida (efeito colateral de E/S)
        if "N" in live or "Z" in live:
            ctx.t = True
            L.append("t = ((lx_u32)cpu->%s - m) & 0xFF;" % reg)
        if "C" in live:
            L.append("cpu->c = (lx_u8)(cpu->%s >= m);" % reg)
        L += _set_nz(live, "(lx_u8)t")
    elif op.sem in ("bit", "bit_imm"):
        L += _read_operand(insn, ctx)
        if not live:
            L.append("(void)m;")
        if "Z" in live:
            L.append("cpu->zsrc = (lx_u8)(cpu->a & m);")
        if "N" in live:
            L.append("cpu->nsrc = (lx_u8)m;")
        if "V" in live:
            L.append("cpu->v = (lx_u8)((m >> 6) & 1);")
    elif op.sem in ("inc", "dec", "asl", "lsr", "rol", "ror"):
        L += _emit_rmw(op, ctx)
    elif op.sem in ("tsb", "trb"):
        ctx.t = True
        L += _read_operand(insn, ctx)
        if "Z" in live:
            L.append("cpu->zsrc = (lx_u8)(cpu->a & m);")
        L.append("t = %s;" % ("m | cpu->a" if op.sem == "tsb" else "m & ~(lx_u32)cpu->a & 0xFF"))
        L += _store_after_read(insn, "(lx_u8)t")
    elif insn.flow != "seq":
        L += _emit_terminator(op, ctx)
    else:
        L += _emit_implied(op, ctx)
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
    if sem == "brk":
        ret = insn.next_addr                    # BRK tem 2 bytes: empilha addr+2 (RTI NÃO soma 1)
        return ["lx_push8(&cpu->s, 0x%02X);" % (ret >> 8), "lx_push8(&cpu->s, 0x%02X);" % (ret & 0xFF),
                "lx_push8(&cpu->s, (lx_u8)(lx_cpu_pack_p(cpu) | 0x10));   /* B=1 */",
                "cpu->i = 1;", "cpu->d = 0;       /* 65C02: BRK limpa D */",
                "pc = lx_rd16(0xFFFE);"]
    if sem == "rti":
        ctx.t = True
        return ["lx_cpu_unpack_p(cpu, lx_pull8(&cpu->s));", "cpu->b = 0;",
                "t = lx_pull8(&cpu->s);", "t |= (lx_u32)lx_pull8(&cpu->s) << 8;", "pc = t & 0xFFFF;"]
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
           "lx_u32 %s(LxCpu *cpu, lx_u32 entry)" % name, "{"]
    out += ["    " + d for d in decls]
    if decls:
        out.append("")
    out.append("    (void)entry;                      /* fase 1: um bloco por função, sem sub-entradas */")
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


def _entry_row(addr, sub, flags, fn):
    f = "%s" % flags if flags else "0"
    return "    { 0x%04X, 0x%04X | %s, %s }" % (addr, (sub << 4) & 0xFFFF, f, fn)


def emit_functions(overlay_id: int, cfg, ops_by_block, phase: int = 2, max_blocks=None):
    """Emite as FUNÇÕES do overlay. Retorna (texto, {endereço_do_bloco: (nome_da_função, sub)}).
    phase 1: um bloco por função (trampolim por bloco). phase 2: rotinas com blocos fundidos (docs/04 §3.2)."""
    parts, where = [], {}
    if phase == 1:
        for start in cfg.starts:
            nm = block_fn_name(overlay_id, start)
            parts.append(emit_block(nm, ops_by_block[start], start))
            where[start] = (nm, 0)
    else:
        from .routines import DEFAULT_MAX_BLOCKS, partition
        part = partition(cfg, DEFAULT_MAX_BLOCKS if max_blocks is None else max_blocks)
        for root, blocks in part.items():
            nm = block_fn_name(overlay_id, root)
            parts.append(emit_routine(nm, cfg, ops_by_block, root, blocks, set(part)))
            order = [root] + [x for x in blocks if x != root]
            for sub, blk in enumerate(order):
                where[blk] = (nm, sub)
    return "\n".join(parts), where


def emit_overlay(overlay_id: int, cfg, ops_by_block, cart_offset: int = 0, phase: int = 2, max_blocks=None) -> str:
    """Emite funções + tabela de despacho + descritor LxOverlay. A tabela lista TODOS os líderes (cada um com sua
    sub-entrada), porque um YIELD no meio de uma rotina precisa poder ser retomado dali."""
    text, where = emit_functions(overlay_id, cfg, ops_by_block, phase, max_blocks)
    rows = [_entry_row(st, where[st][1], "LX_DE_RETADDR" if cfg.blocks[st].retaddr else "", where[st][0])
            for st in cfg.starts]
    return "\n".join([
        text,
        "static const LxDispatchEntry lx_ov%d_entries[] = {\n%s\n};\n" % (overlay_id, ",\n".join(rows)),
        "const LxOverlay lx_ov%d = {\n    %d, 0x%04X, 0x%04X, %d, 0x%X, 0, lx_ov%d_entries\n};\n" %
        (overlay_id, overlay_id, cfg.org, cfg.size, len(cfg.starts), cart_offset, overlay_id)])


def emit_unit(blocks: Iterable[Tuple[str, Sequence[IrOp], int]]) -> str:
    """Emite um arquivo .c completo com vários blocos: [(nome, ops, org), ...]."""
    parts = [_HEADER % {"ver": __version__, "abi": ABI_VERSION}]
    for name, ops, org in blocks:
        parts.append(emit_block(name, ops, org))
    return "\n".join(parts)


# =====================================================================================================
# FASE 2 — rotinas: blocos fundidos por goto, registradores e flags em VARIÁVEIS LOCAIS
# Contrato (ABI v3):  lx_u32 f(LxCpu *cpu, lx_u32 entry)
#   - entrada: carrega só as variáveis usadas; 'entry' escolhe o líder onde começar (0 = raiz);
#   - teste de evento (cyc >= ev) APÓS cada instrução de fluxo (desvio, salto, JSR, RTS...) e em toda saída;
#     NÃO há teste entre blocos que só caem um no outro (é a mudança de fronteira que o oráculo conhece: 'raízes');
#   - saída única L_exit: grava as variáveis escritas e cpu->cycles; se cyc >= ev chama lx_sched_service (chamada final).
# =====================================================================================================
_P2_REGS = ("a", "x", "y", "s", "c", "v", "d", "i", "nsrc", "zsrc")
_REG_RE = re.compile(r"cpu->(a|x|y|s|c|v|d|i|nsrc|zsrc)\b")
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_WRITE_RE = {n: re.compile(r"\b%s\s*(?:\+|-|\||&|\^|<<|>>)?=(?!=)" % n) for n in _P2_REGS}


def _p2_line(line):
    """Converte uma linha emitida na forma da fase 1 (campos de LxCpu) para a fase 2 (variáveis locais)."""
    if line.strip().startswith("cpu->b = 0;"):
        return None                                           # B não é estado: só existe no P empilhado
    line = re.sub(r"lx_push8\(&cpu->s, (.+?)\);", r"LX_PUSH8(s, \1);", line)
    line = line.replace("lx_pull8(&cpu->s)", "LX_PULL8(s)")
    line = line.replace("lx_cpu_pack_p(cpu)", "LX_PACK_P(nsrc, v, d, i, zsrc, c)")
    line = re.sub(r"lx_cpu_unpack_p\(cpu, (.+)\);", r"LX_UNPACK_P(\1, nsrc, zsrc, v, d, i, c);", line)
    line = re.sub(r"lx_(adc|sbc)_dec\(cpu, \(lx_u8\)m\);",
                  r"t = lx_\1_dec_v(a, c, m); a = t & 0xFF; c = (t >> 8) & 1; v = (t >> 9) & 1; nsrc = a; zsrc = a;", line)
    line = line.replace("cpu->cycles", "cyc")
    return _REG_RE.sub(r"\1", line)


def _p2_terminator(op, ctx, intra, label, nxt_physical, base):
    """Transferência de controle da fase 2. 'intra' = endereços de blocos da MESMA rotina; 'nxt_physical' = endereço do
    bloco que vem fisicamente a seguir na função (cair nele não precisa de goto); 'base' = ciclos base do bloco."""
    insn, sem = op.insn, op.sem

    def go(tgt, with_check=True):
        """Salta para tgt: dentro da rotina com teste de evento; fora, pela saída única (que testa)."""
        if tgt in intra:
            lines = (["if (cyc >= ev) { pc = 0x%04X; goto L_exit; }" % tgt] if with_check else [])
            return lines + ["goto %s;" % label(tgt)]
        return ["pc = 0x%04X;" % tgt, "goto L_exit;"]

    L = ["cyc += %d;" % base]
    if sem in _BRANCH_COND:
        ctx_taken = _taken_extra(insn)
        L.append("if (%s) {" % _REG_RE.sub(r"\1", _BRANCH_COND[sem]))     # condição sobre as variáveis LOCAIS
        L.append("    cyc += %d;" % ctx_taken)
        L += ["    " + x for x in go(insn.target)]
        L.append("}")
        nxt = insn.next_addr
        if nxt in intra:
            L.append("if (cyc >= ev) { pc = 0x%04X; goto L_exit; }" % nxt)
            if nxt != nxt_physical:
                L.append("goto %s;" % label(nxt))
        else:
            L += ["pc = 0x%04X;" % nxt, "goto L_exit;"]
        return L
    if sem == "bra":
        L.append("cyc += %d;" % _taken_extra(insn))
        return L + go(insn.target)
    if sem == "jmp":
        return L + go(insn.target)
    # saídas dinâmicas / chamadas: sempre pela saída única
    lines = _emit_terminator(op, ctx)
    return L + [ln for ln in (_p2_line(x) for x in lines) if ln is not None] + ["goto L_exit;"]


def emit_routine(name, cfg, ops_by_block, root, blocks, roots):
    """Uma função C para a rotina 'root' com os blocos 'blocks' fundidos."""
    order = [root] + [b for b in blocks if b != root]
    sub_of = {blk: i for i, blk in enumerate(order)}
    intra = set(blocks)
    emit_order = sorted(blocks)                                  # ordem física = endereço crescente
    multi = len(blocks) > 1

    # alvos de goto internos (para saber quais rótulos existem)
    referenced = set(emit_order) if multi else set()
    for blk in emit_order:
        b = cfg.blocks[blk]
        if b.kind in ("branch", "jump") and any(t in intra and t == blk for t in b.succs):
            referenced.add(blk)                                   # laço de um bloco só

    def label(a):
        return "L_%04X" % a

    ctx = _Ctx()
    ctx.pc = True
    body = []
    for idx, blk in enumerate(emit_order):
        ops = ops_by_block[blk]
        nxt_physical = emit_order[idx + 1] if idx + 1 < len(emit_order) else None
        if blk in referenced:
            body.append(label(blk) + ":")
        total = sum(o.insn.cycles for o in ops)
        for i, op in enumerate(ops):
            if op.insn.flow != "seq" and i != len(ops) - 1:
                raise ValueError("instrução de fluxo no meio do bloco em $%04X" % op.insn.addr)
        term = ops[-1] if ops[-1].insn.flow != "seq" else None
        for op in (ops[:-1] if term else ops):
            for ln in _emit_op(op, ctx):
                ln = _p2_line(ln)
                if ln is not None:
                    body.append("    " + ln if not ln.startswith("/*") else "    " + ln)
        if term is not None:
            # a própria instrução terminadora também gera linhas de operando? (não: só controle)
            body.append("    /* $%04X  %s */" % (term.insn.addr, term.insn.text()))
            for ln in _p2_terminator(term, ctx, intra, label, nxt_physical, total):
                body.append("    " + ln)
        else:
            last = ops[-1].insn
            nxt = last.next_addr
            body.append("    cyc += %d;" % total)
            if nxt in intra:
                if nxt == root:                       # cair numa RAIZ (mesmo a da própria rotina, se houver blocos em
                    body.append("    if (cyc >= ev) { pc = 0x%04X; goto L_exit; }" % nxt)   # endereço menor) é fronteira
                if nxt != nxt_physical or nxt == root:
                    body.append("    goto %s;" % label(nxt))
            else:
                body += ["    pc = 0x%04X;" % nxt, "    goto L_exit;"]

    text = "\n".join(body)
    plain = _COMMENT_RE.sub("", text)
    referenced_regs = [n for n in _P2_REGS if re.search(r"\b%s\b" % n, plain)]
    if "LX_UNPACK_P" in plain:
        referenced_regs = list(_P2_REGS[4:]) + [n for n in referenced_regs if n not in _P2_REGS[4:]]
    if "LX_PACK_P" in plain:
        for n in ("nsrc", "v", "d", "i", "zsrc", "c"):
            if n not in referenced_regs:
                referenced_regs.append(n)
    referenced_regs = [n for n in _P2_REGS if n in referenced_regs]
    written = set(n for n in referenced_regs if _WRITE_RE[n].search(plain))
    if "LX_PUSH8(s" in plain or "LX_PULL8(s" in plain:
        written.add("s")
        if "s" not in referenced_regs:
            referenced_regs.append("s")
    if "LX_UNPACK_P" in plain:
        written |= {"nsrc", "zsrc", "v", "d", "i", "c"}
    referenced_regs = [n for n in _P2_REGS if n in referenced_regs]

    decls = ["lx_u32 %s;" % ", ".join(referenced_regs + ["cyc", "ev", "pc"])]
    for flag, vname in ((ctx.ea, "ea"), (ctx.m, "m"), (ctx.t, "t")):
        if flag:
            decls.append("lx_u32 %s;" % vname)
    nroots = len(order)
    out = ["/* rotina $%04X: %d bloco(s) fundido(s), %d instrução(ões) */" %
           (root, nroots, sum(len(ops_by_block[b]) for b in blocks)),
           "lx_u32 %s(LxCpu *cpu, lx_u32 entry)" % name, "{"]
    out += ["    " + d for d in decls]
    out.append("")
    for n in referenced_regs:
        out.append("    %s = cpu->%s;" % (n, n))
    out.append("    cyc = cpu->cycles;")
    out.append("    ev = cpu->next_event;")
    out.append("    pc = 0;")
    if multi:
        out.append("    switch (entry) {")
        for blk in order:
            out.append("    case %d: goto %s;" % (sub_of[blk], label(blk)))
        out.append("    default: goto %s;" % label(root))
        out.append("    }")
    else:
        out.append("    (void)entry;")
    out.append("")
    out.append(text)
    out.append("")
    out.append("L_exit:")
    for n in referenced_regs:
        if n in written:
            out.append("    cpu->%s = (lx_u8)%s;" % (n, n))
    out.append("    cpu->cycles = cyc;")
    out.append("    if (cyc >= ev)")
    out.append("        return lx_sched_service(cpu, pc);")
    out.append("    return pc;")
    out.append("}")
    return "\n".join(out) + "\n"
