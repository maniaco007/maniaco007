/*
 * lx_platform.h — contrato dos BACKENDS de plataforma.
 *
 * O núcleo (CPU ABI, overlays, HLE do Suzy/Mikey) é idêntico no 3DO e no
 * host. Cada plataforma fornece UMA implementação destas funções, escolhida
 * em tempo de LINK (sem vtable; custo zero):
 *   runtime/platform/3do/   -> DrawCels(), SPORT/VRAM, Portfolio I/O
 *   runtime/platform/host/  -> rasterizador de software + SDL opcional
 *
 * Vantagem central: o MESMO código gerado pelo lynx2c roda no PC, onde pode
 * ser comparado quadro a quadro com um emulador de referência (docs/02 §9).
 */
#ifndef LX_PLATFORM_H
#define LX_PLATFORM_H

#include "lx_types.h"
#include "lx_cel.h"

/* ---- Vídeo ---------------------------------------------------------------------- */
int  lx_gfx_init(void);
void lx_gfx_shutdown(void);

/* Registra uma superfície de desenho associada a um endereço VIDBASE do Lynx.
 * O backend 3DO mapeia para um BitmapItem (VRAM); o host, para um vetor RGB. */
int  lx_gfx_surface_bind(lx_u8 surface, lx_u16 lynx_vidbase);

/* Paleta ativa (Mikey GREEN/BLUERED, 16 cores) já convertida p/ RGB555. */
void lx_gfx_set_palette(const lx_u16 rgb555[16]);

/* Submete 'n' Cels EM ORDEM (a ordem é semântica no Lynx). O backend 3DO
 * encadeia CCBs (NextPtr/LAST) e chama DrawCels; Cels com LX_CELF_FALLBACK
 * são entregues ao rasterizador de software e o resultado é mesclado na
 * superfície (modo LX_FB_SOFT/fallback). */
void lx_gfx_submit_cels(const LxCelDesc *cels, lx_u32 n);

/* Fundo opcional: o framebuffer 4bpp da RAM Lynx (80 bytes/linha) como Cel
 * de tela cheia, ZERO-COPY quando 'lynx_fb' estiver alinhado a 32 bits
 * (modo LX_FB_UNDER). */
void lx_gfx_submit_fb_layer(const lx_u8 *lynx_fb, lx_u8 surface);

/* Apresenta (flip) a superfície indicada. Bloqueia p/ sincronismo de vblank. */
void lx_gfx_present(lx_u8 surface);

/* ---- Entrada / tempo / disco ----------------------------------------------------- */
/* Retorna o byte no formato do registrador JOYSTICK ($FCB0) já com
 * remapeamento de rotação do cartucho aplicado. */
lx_u8  lx_input_joystick(void);
lx_u8  lx_input_switches(void);          /* SWITCHES ($FCB1): pause, opção 1/2 */

lx_u32 lx_time_ms(void);

/* Carrega o arquivo do disco (CD no 3DO) inteiro em memória; devolve ponteiro
 * ou NULL. Usado no boot p/ cartucho (lxdata.bin) e assets cozidos. */
const lx_u8 *lx_file_load(const char *path, lx_u32 *out_size);

#endif /* LX_PLATFORM_H */
