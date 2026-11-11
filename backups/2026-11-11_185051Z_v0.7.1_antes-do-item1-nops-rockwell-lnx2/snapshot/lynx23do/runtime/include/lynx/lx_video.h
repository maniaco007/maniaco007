/*
 * lx_video.h — vídeo do Mikey: paleta de 16 cores e DMA de vídeo (independente de plataforma).
 *
 * Layout CONFIRMADO no emulador Handy (mikie.cpp / lynxdef.h, lidos como dado de referência):
 *   $FDA0-$FDAF GREEN0..F    : verde = byte & $0F
 *   $FDB0-$FDBF BLUERED0..F  : AZUL = byte >> 4 (nibble alto), VERMELHO = byte & $0F
 *   $FD92 DISPCTL, $FD94/$FD95 DISPADR (L/H) = endereço do framebuffer na RAM do Lynx
 *   framebuffer 4 bpp, 80 bytes/linha, 102 linhas; pixel da ESQUERDA = nibble ALTO
 *   (mesma ordem do 4 bpp codificado do 3DO: o framebuffer serve de Cel de tela cheia, sem cópia)
 * Cada componente de 4 bits vira 5 bits por (v << 1) | (v >> 3) (a mesma expansão do Handy: $F -> 31) e o
 * resultado é RGB 1:5:5:5 do 3DO, R nos bits 14-10 (MakeRGB15 do SDK: (r<<10)|(g<<5)|b).
 */
#ifndef LX_VIDEO_H
#define LX_VIDEO_H

#include "lx_types.h"
#include "lx_config.h"

#define LX_REG_DISPCTL   0xFD92UL
#define LX_REG_DISPADRL  0xFD94UL
#define LX_REG_DISPADRH  0xFD95UL
#define LX_REG_GREEN0    0xFDA0UL
#define LX_REG_BLUERED0  0xFDB0UL

#define LX_DISPCTL_DMA   0x01      /* bit 0: DMA de vídeo ligado (DMAEnable) */

void   lx_video_reset(void);

/* Tratam apenas os registradores de vídeo; devolvem 1 se o endereço era deles, 0 caso contrário. */
int    lx_video_write(lx_u32 addr, lx_u8 val);
int    lx_video_read (lx_u32 addr, lx_u8 *out);

lx_u16 lx_video_rgb555(unsigned pen);          /* cor do pen 0..15 em RGB555 do 3DO */
void   lx_video_plut(lx_u16 out[LX_PALETTE_SIZE]);
lx_u32 lx_video_dispadr(void);                 /* endereço do framebuffer na RAM do Lynx */
lx_u8  lx_video_dispctl(void);
int    lx_video_dma_enabled(void);

/* Contador que cresce a cada escrita de paleta: permite à plataforma refazer a PLUT só quando mudou. */
lx_u32 lx_video_palette_epoch(void);

#endif /* LX_VIDEO_H */
