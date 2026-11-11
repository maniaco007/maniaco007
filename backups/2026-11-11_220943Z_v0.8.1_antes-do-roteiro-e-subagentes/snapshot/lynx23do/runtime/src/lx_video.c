/* lx_video.c — ver lx_video.h (layout confirmado no Handy). */
#include "lynx/lx_video.h"

static lx_u8  g_green[LX_PALETTE_SIZE];
static lx_u8  g_bluered[LX_PALETTE_SIZE];
static lx_u32 g_dispadr;
static lx_u8  g_dispctl;
static lx_u32 g_epoch;

void lx_video_reset(void)
{
    unsigned i;
    for (i = 0; i < LX_PALETTE_SIZE; i++) { g_green[i] = 0; g_bluered[i] = 0; }
    g_dispadr = 0;
    g_dispctl = 0;
    g_epoch = 1;
}

int lx_video_write(lx_u32 addr, lx_u8 val)
{
    if (addr >= LX_REG_GREEN0 && addr < LX_REG_GREEN0 + LX_PALETTE_SIZE) {
        g_green[addr - LX_REG_GREEN0] = (lx_u8)(val & 0x0F);
        g_epoch++;
        return 1;
    }
    if (addr >= LX_REG_BLUERED0 && addr < LX_REG_BLUERED0 + LX_PALETTE_SIZE) {
        g_bluered[addr - LX_REG_BLUERED0] = val;
        g_epoch++;
        return 1;
    }
    if (addr == LX_REG_DISPADRL) { g_dispadr = (g_dispadr & 0xFF00UL) | val; return 1; }
    if (addr == LX_REG_DISPADRH) { g_dispadr = (g_dispadr & 0x00FFUL) | ((lx_u32)val << 8); return 1; }
    if (addr == LX_REG_DISPCTL)  { g_dispctl = val; return 1; }
    return 0;
}

int lx_video_read(lx_u32 addr, lx_u8 *out)
{
    if (addr >= LX_REG_GREEN0 && addr < LX_REG_GREEN0 + LX_PALETTE_SIZE) { *out = g_green[addr - LX_REG_GREEN0]; return 1; }
    if (addr >= LX_REG_BLUERED0 && addr < LX_REG_BLUERED0 + LX_PALETTE_SIZE) { *out = g_bluered[addr - LX_REG_BLUERED0]; return 1; }
    if (addr == LX_REG_DISPADRL) { *out = (lx_u8)(g_dispadr & 0xFF); return 1; }
    if (addr == LX_REG_DISPADRH) { *out = (lx_u8)(g_dispadr >> 8); return 1; }
    if (addr == LX_REG_DISPCTL)  { *out = g_dispctl; return 1; }
    return 0;
}

static lx_u32 expand5(lx_u32 v4) { return (v4 << 1) | (v4 >> 3); }      /* 4 -> 5 bits, $F -> 31 */

lx_u16 lx_video_rgb555(unsigned pen)
{
    lx_u32 r, g, b;
    pen &= 0x0F;
    r = expand5(g_bluered[pen] & 0x0F);
    b = expand5((lx_u32)(g_bluered[pen] >> 4));
    g = expand5(g_green[pen] & 0x0F);
    return (lx_u16)((r << 10) | (g << 5) | b);                           /* MakeRGB15(r,g,b) do SDK 3DO */
}

void lx_video_plut(lx_u16 out[LX_PALETTE_SIZE])
{
    unsigned i;
    for (i = 0; i < LX_PALETTE_SIZE; i++) out[i] = lx_video_rgb555(i);
}

lx_u32 lx_video_dispadr(void)        { return g_dispadr; }
lx_u8  lx_video_dispctl(void)        { return g_dispctl; }
int    lx_video_dma_enabled(void)    { return (g_dispctl & LX_DISPCTL_DMA) != 0; }
lx_u32 lx_video_palette_epoch(void)  { return g_epoch; }
