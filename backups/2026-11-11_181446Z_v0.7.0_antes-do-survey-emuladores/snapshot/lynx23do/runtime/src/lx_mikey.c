/*
 * lx_mikey.c — Mikey MÍNIMO (M1): vídeo/paleta de verdade (lx_video.c); o resto é um arquivo de registradores que
 * devolve o último valor escrito. FALTAM: timers, IRQ, UART, áudio, SYSCTL1/cartucho. Ver lx_machine.h.
 */
#include "lynx/lx_mikey.h"
#include "lynx/lx_video.h"

static lx_u8 g_mikey[256];

lx_u8 lx_mikey_read(lx_u32 addr)
{
    lx_u8 v;
    if (lx_video_read(addr, &v)) return v;
    return g_mikey[addr & 0xFF];
}

void lx_mikey_write(lx_u32 addr, lx_u8 val)
{
    if (lx_video_write(addr, val)) return;
    g_mikey[addr & 0xFF] = val;
}
