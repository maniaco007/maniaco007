/*
 * lx_dispatch.c — trampolim (lx_run), despacho por PC e tratamento de PC não resolvido.
 * Contrato: lx_cpu_abi.h / docs/02 §7 (fase 1: um bloco = uma função que devolve o próximo PC).
 */
#include "lynx/lx_cpu_abi.h"
#include "lynx/lx_overlay.h"

lx_u32 lx_unresolved_pc = 0xFFFFFFFFUL;
lx_u32 lx_unresolved_count;

void lx_unresolved(lx_u32 pc)
{
    lx_unresolved_pc = pc;
    lx_unresolved_count++;
}

/* busca binária em vetor ORDENADO por addr */
static const LxDispatchEntry *find_entry(const LxOverlay *ov, lx_u32 pc)
{
    lx_u32 lo = 0, hi = ov->n_entries;
    while (lo < hi) {
        lx_u32 mid = (lo + hi) >> 1;
        lx_u32 a = ov->entries[mid].addr;
        if (a == pc) return &ov->entries[mid];
        if (a < pc) lo = mid + 1; else hi = mid;
    }
    return 0;
}

lx_u32 lx_dispatch(LxCpu *cpu, lx_u32 pc)
{
    const LxHook *h;
    const LxOverlay *ov;
    const LxDispatchEntry *e;

    pc &= 0xFFFFUL;
    h = lx_hook_find((lx_u16)pc);
    if (h) return h->fn(cpu);
    ov = lx_overlay_at((lx_u16)pc);
    e = ov ? find_entry(ov, pc) : 0;
    if (!e) {
        lx_unresolved(pc);
        return LX_PC_HALT;
    }
    return e->fn(cpu);
}

lx_u32 lx_run(LxCpu *cpu, lx_u32 pc)
{
    for (;;) {
        lx_u32 r = lx_dispatch(cpu, pc);
        if (r >= 0x10000UL) return r;     /* LX_PC_RETURN/YIELD/HALT */
        pc = r;
    }
}
