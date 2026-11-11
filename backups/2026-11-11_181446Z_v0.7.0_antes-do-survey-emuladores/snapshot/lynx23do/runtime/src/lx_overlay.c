/*
 * lx_overlay.c — overlays ativos, hooks e carga de segmentos do cartucho.
 *
 * PENDENTE: cartucho serial (lx_cart_* / RCART0-1) — fase do Suzy/carregador.
 */
#include <string.h>

#include "lynx/lx_overlay.h"
#include "lynx/lx_mem.h"

static const LxCart *g_cart;
static const LxOverlay *g_active[LX_MAX_OVERLAYS];
static unsigned g_n_active;

int lx_overlay_init(const LxCart *cart)
{
    g_cart = cart;
    g_n_active = 0;
    if (lx_program.abi_version != (lx_u32)LX_ABI_VERSION) return -1;
    if (cart && lx_program.cart_size != cart->size) return -2;
    return 0;
}

void lx_overlay_reset(void) { g_n_active = 0; }

static int overlaps(const LxOverlay *a, const LxOverlay *b)
{
    lx_u32 a0 = a->load_addr, a1 = a0 + a->size, b0 = b->load_addr, b1 = b0 + b->size;
    return a0 < b1 && b0 < a1;
}

void lx_overlay_activate(const LxOverlay *ov)
{
    unsigned i, j = 0;
    for (i = 0; i < g_n_active; i++)
        if (!overlaps(g_active[i], ov)) g_active[j++] = g_active[i];
    g_n_active = j;
    if (g_n_active < LX_MAX_OVERLAYS) g_active[g_n_active++] = ov;
}

void lx_overlay_load(lx_u16 overlay_id, lx_u32 cart_off, lx_u16 dest, lx_u16 len)
{
    unsigned i;
    if (!g_cart || cart_off + len > g_cart->size || (lx_u32)dest + len > LX_RAM_SIZE) return;
    memcpy(&lx_ram[dest], g_cart->data + cart_off, len);
    for (i = 0; i < lx_program.n_overlays; i++)
        if (lx_program.overlays[i].id == overlay_id) { lx_overlay_activate(&lx_program.overlays[i]); return; }
}

const LxOverlay *lx_overlay_at(lx_u16 addr)
{
    unsigned i;
    for (i = 0; i < g_n_active; i++) {
        const LxOverlay *o = g_active[i];
        if (addr >= o->load_addr && (lx_u32)addr < (lx_u32)o->load_addr + o->size) return o;
    }
    return 0;
}

lx_s32 lx_overlay_cart_offset_of(lx_u16 addr)
{
    const LxOverlay *o = lx_overlay_at(addr);
    return o ? (lx_s32)(o->cart_offset + (lx_u32)(addr - o->load_addr)) : -1;
}

const LxHook *lx_hook_find(lx_u16 addr)
{
    unsigned i;
    const LxOverlay *o = lx_overlay_at(addr);
    for (i = 0; i < lx_program.n_hooks; i++) {
        const LxHook *h = &lx_program.hooks[i];
        if (h->addr == addr && (h->overlay_id == 0xFFFF || (o && h->overlay_id == o->id))) return h;
    }
    return 0;
}
