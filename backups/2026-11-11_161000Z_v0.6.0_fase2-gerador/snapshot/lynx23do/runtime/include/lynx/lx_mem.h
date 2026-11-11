/*
 * lx_mem.h — modelo de memória do Lynx (64 KB) visto pelo código gerado.
 *
 * Mapa do Lynx (resumo; ver docs/04-orcamento-memoria-2mb.md):
 *   $0000-$FBFF  RAM (zero page $00xx, pilha $01xx)
 *   $FC00-$FCFF  Suzy  (sprites, matemática, joystick, cartucho)   -> HLE
 *   $FD00-$FDFF  Mikey (timers, áudio, paleta, vídeo DMA, UART)    -> HLE
 *   $FE00-$FFF7  ROM de boot (sobreposta; normalmente desligada pelo jogo)
 *   $FFF8-$FFFF  RAM por baixo + vetores; $FFF9 = MAPCTL
 * O cartucho NÃO é endereçável: é lido em série via RCART0/RCART1 (Suzy).
 *
 * Estratégia de acesso:
 *   - O lynx2c classifica cada operando ABSOLUTO em tempo de tradução:
 *       endereço < $FC00           -> lx_ram[addr] direto (zero custo extra)
 *       endereço em $FC00-$FCFF    -> lx_suzy_write()/lx_suzy_read() direto
 *       endereço em $FD00-$FDFF    -> lx_mikey_write()/lx_mikey_read() direto
 *   - Operandos indiretos/indexados têm região desconhecida: usam lx_rd8()/
 *     lx_wr8() abaixo (1 comparação no caminho comum).
 *   - Zero page e pilha SEMPRE são RAM (acesso direto, com wrap de 8 bits).
 */
#ifndef LX_MEM_H
#define LX_MEM_H

#include "lx_types.h"
#include "lx_config.h"

/* RAM do Lynx: vetor de bytes (endianness-neutro). Definida em runtime/src/lx_mem.c. */
extern lx_u8 lx_ram[LX_RAM_SIZE];

#define LX_IO_BASE     0xFC00UL
#define LX_SUZY_BASE   0xFC00UL
#define LX_SUZY_END    0xFCFFUL
#define LX_MIKEY_BASE  0xFD00UL
#define LX_MIKEY_END   0xFDFFUL
#define LX_MAPCTL      0xFFF9UL

/* caminho lento (E/S, ROM de boot, vetores sob MAPCTL) — runtime/src/lx_mem.c */
lx_u8 lx_io_read (lx_u32 addr);
void  lx_io_write(lx_u32 addr, lx_u8 val);

/* acesso genérico 8 bits (addr já mascarado em 16 bits pelo chamador) */
LX_INLINE lx_u8 lx_rd8(lx_u32 addr)
{
    return (addr < LX_IO_BASE) ? lx_ram[addr] : lx_io_read(addr);
}
LX_INLINE void lx_wr8(lx_u32 addr, lx_u8 val)
{
    if (addr < LX_IO_BASE) lx_ram[addr] = val; else lx_io_write(addr, val);
}

/* 16 bits little-endian composto de bytes (NUNCA cast de ponteiro: o 3DO é BE) */
LX_INLINE lx_u32 lx_rd16(lx_u32 addr)
{
    return (lx_u32)lx_rd8(addr) | ((lx_u32)lx_rd8((addr + 1) & 0xFFFFUL) << 8);
}
LX_INLINE void lx_wr16(lx_u32 addr, lx_u32 val)
{
    lx_wr8(addr, (lx_u8)(val & 0xFF));
    lx_wr8((addr + 1) & 0xFFFFUL, (lx_u8)((val >> 8) & 0xFF));
}

/* ponteiro de zero page: (zp) e (zp),Y — wrap em 8 bits como no 65C02 */
LX_INLINE lx_u32 lx_zp_ptr(lx_u32 zp)
{
    return (lx_u32)lx_ram[zp & 0xFF] | ((lx_u32)lx_ram[(zp + 1) & 0xFF] << 8);
}

/* pilha em $0100-$01FF */
LX_INLINE void lx_push8(lx_u8 *s, lx_u8 val) { lx_ram[0x100 | *s] = val; (*s)--; }
LX_INLINE lx_u8 lx_pull8(lx_u8 *s)           { (*s)++; return lx_ram[0x100 | *s]; }

/* região estática de um endereço, para uso do lynx2c e de asserts de debug */
#define LX_REGION_RAM    0
#define LX_REGION_SUZY   1
#define LX_REGION_MIKEY  2
#define LX_REGION_ROMVEC 3
LX_INLINE int lx_region_of(lx_u32 a)
{
    if (a < LX_IO_BASE)    return LX_REGION_RAM;
    if (a <= LX_SUZY_END)  return LX_REGION_SUZY;
    if (a <= LX_MIKEY_END) return LX_REGION_MIKEY;
    return LX_REGION_ROMVEC;
}

#endif /* LX_MEM_H */
