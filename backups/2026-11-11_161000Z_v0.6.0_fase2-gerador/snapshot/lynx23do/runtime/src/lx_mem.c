/*
 * lx_mem.c — RAM do Lynx e roteamento do caminho lento de E/S ($FC00-$FFFF).
 *
 * O roteamento DEVE espelhar a classificação estática do lynx2c (emit_c.py:
 * _static_read/_static_write) e lx_region_of() em lx_mem.h:
 *   $FC00-$FCFF -> Suzy    $FD00-$FDFF -> Mikey    $FE00-$FFFF -> ROM/vetores
 *
 * PENDENTE (fase do Mikey/boot): sobreposição da ROM de boot ($FE00-$FFF7) e
 * vetores sob controle de MAPCTL ($FFF9), bits de desligamento de Suzy/Mikey.
 * Por ora, $FE00-$FFFF leem/escrevem a RAM por baixo (jogos desligam a ROM de boot).
 */
#include "lynx/lx_mem.h"
#include "lynx/lx_suzy.h"
#include "lynx/lx_mikey.h"

lx_u8 lx_ram[LX_RAM_SIZE];

lx_u8 lx_io_read(lx_u32 addr)
{
    if (addr <= LX_SUZY_END)  return lx_suzy_read(addr);
    if (addr <= LX_MIKEY_END) return lx_mikey_read(addr);
    return lx_ram[addr & 0xFFFF];
}

void lx_io_write(lx_u32 addr, lx_u8 val)
{
    if (addr <= LX_SUZY_END)       lx_suzy_write(addr, val);
    else if (addr <= LX_MIKEY_END) lx_mikey_write(addr, val);
    else                           lx_ram[addr & 0xFFFF] = val;
}
