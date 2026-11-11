/*
 * lx_suzy_min.c — Suzy MÍNIMO (M1): JOYSTICK e SWITCHES vêm da plataforma; o resto é arquivo de registradores.
 * SPRGO ($FC91, bit 0) é CONTADO e IGNORADO: o motor de sprites (SCB -> Cel) ainda não existe (docs/03, M3).
 * Será substituído por lx_suzy.c quando o HLE do Suzy for implementado.
 */
#include "lynx/lx_machine.h"
#include "lynx/lx_platform.h"
#include "lynx/lx_suzy.h"

static lx_u8 g_suzy[256];
lx_u32 lx_suzy_min_sprgo_ignored;

lx_u8 lx_suzy_read(lx_u32 addr)
{
    if (addr == LX_R_JOYSTICK) return lx_input_joystick();
    if (addr == LX_R_SWITCHES) return lx_input_switches();
    return g_suzy[addr & 0xFF];
}

void lx_suzy_write(lx_u32 addr, lx_u8 val)
{
    if (addr == LX_R_SPRGO && (val & 1)) lx_suzy_min_sprgo_ignored++;
    g_suzy[addr & 0xFF] = val;
}
