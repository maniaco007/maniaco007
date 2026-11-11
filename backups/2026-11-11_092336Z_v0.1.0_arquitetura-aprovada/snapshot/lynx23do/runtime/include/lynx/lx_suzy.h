/*
 * lx_suzy.h — HLE (High-Level Emulation) do chip Suzy.
 *
 * Idéia: o código 65C02 traduzido continua escrevendo nos registradores e
 * montando SCBs na RAM EXATAMENTE como no original. Nada é reescrito no jogo.
 * Quando o código escreve SPRGO ($FC91, bit0=1), o runtime NÃO simula o
 * desenho pixel a pixel: percorre a cadeia de SCBs, converte cada SCB em um
 * Cel (LxCelDesc), e entrega a cadeia ao Cel Engine (DrawCels) via backend.
 *
 *   65C02 traduzido ──escreve──▶ regs Suzy / SCBs na lx_ram
 *                                        │ SPRGO
 *                                        ▼
 *            lx_suzy_sprgo(): para cada SCB da cadeia
 *               lx_suzy_scb_decode()      SCB (RAM) + regs persistentes -> LxScb
 *               lx_suzy_sprite_source()   dados do sprite -> pixels cozidos (cache)
 *               lx_suzy_scb_to_cel()      LxScb -> LxCelDesc  (matriz, PLUT, blend)
 *               lx_suzy_coll_record()     colisão (bbox/pixel) em software
 *                                        │
 *                                        ▼
 *            fila de Cels (LX_SCHED_DEFERRED) ──lx_gfx_submit_cels()──▶ DrawCels
 *
 * Fórmulas de mapeamento (detalhadas em docs/03-hle-suzy.md §3):
 *   escala horizontal  : hdx  = ± HSIZ * S          (HSIZ 8.8, S = LX_VIEW_SCALE)
 *   escala vertical    : vdy  = ± VSIZ * S
 *   tilt  (cisalhar)   : vdx  =   TILT * S           (HPOS += TILT por linha)
 *   stretch(perspectiva): hddx =  STRETCH * S        (HSIZ += STRETCH por linha)
 *   posição            : (xpos,ypos) = view( HPOSSTRT - HOFF, VPOSSTRT - VOFF )
 *   flips/START_*      : sinal de hdx/vdy e escolha do canto de origem
 * Tudo composto com LxViewXform (escala 2x, letterbox, rotação do cartucho).
 */
#ifndef LX_SUZY_H
#define LX_SUZY_H

#include "lx_types.h"
#include "lx_config.h"
#include "lx_cel.h"
#include "lx_suzy_regs.h"

/* ===== 1. Estado e acesso a registradores (chamado pelo código traduzido) ==== */

typedef struct LxSuzyRegs {
    lx_u8  raw[256];            /* espelho bruto $FC00-$FCFF (p/ leituras fiéis)  */
    /* Registradores de 16 bits decodificados (persistem entre SCBs: "reload depth") */
    lx_u16 scbnext, sprdline, hposstrt, vposstrt;
    lx_u16 sprhsiz, sprvsiz, stretch, tilt;
    lx_u16 hoff, voff, vidbas, collbas;
    lx_u8  sprctl0, sprctl1, sprcoll;
    lx_u8  pen[8];              /* tabela pen->índice de cor (8 bytes = 16 nibbles)   */
    lx_u8  sprsys;
} LxSuzyRegs;

extern LxSuzyRegs lx_suzy;

void  lx_suzy_init(void);
lx_u8 lx_suzy_read (lx_u32 addr);              /* addr em $FC00-$FCFF */
void  lx_suzy_write(lx_u32 addr, lx_u8 val);   /* SPRGO dispara lx_suzy_sprgo() */

/* ===== 2. SCB decodificado ===================================================== */

typedef struct LxScb {
    lx_u16 addr;                /* endereço do SCB na lx_ram                     */
    lx_u8  ctl0, ctl1, coll;
    lx_u16 next, data;          /* SCBNEXT, SPRDLINE                              */
    lx_s16 hpos, vpos;          /* posição inicial (com sinal)                    */
    lx_u16 hsiz, vsiz;          /* 8.8                                            */
    lx_u16 stretch, tilt;       /* 8.8                                            */
    lx_u8  pen[8];              /* 16 pens de 4 bits                              */
    /* campos derivados */
    lx_u8  bpp;                 /* 1..4                                           */
    lx_u8  type;                /* LX_SPR_*                                       */
    lx_u8  hflip, vflip, literal, skip, start_up, start_left;
    lx_u8  reload_depth;        /* 0..3                                           */
    lx_u8  reuse_palette;
} LxScb;

/* Decodifica o SCB em 'addr' combinando com os regs persistentes (campos que o
 * SCB não recarrega, conforme reload_depth/reuse_palette, vêm de lx_suzy).
 * Atualiza lx_suzy com o que o hardware também atualizaria. Retorna 0 se o
 * endereço for inválido (fora da RAM / ciclo na cadeia). */
int lx_suzy_scb_decode(lx_u16 addr, LxScb *out);

/* ===== 3. Origem dos pixels ======================================================
 * Prioridade: (1) sprite pré-cozido offline pelo spritecook (procedência
 * conhecida via lx_overlay_cart_offset_of -> tabela de assets);
 * (2) cache de runtime (sprite gerado/descomprimido na RAM; chave = endereço +
 * hash do cabeçalho de linha); (3) conversão on-the-fly -> cache. */
typedef struct LxSpriteSrc {
    const void *pixels;         /* formato LX_PIX_* já alinhado em 32 bits          */
    lx_u16      width, height;  /* em pixels                                        */
    lx_u8       pix_format;     /* LX_PIX_*                                         */
    lx_u8       from_cook;      /* 1 = pré-cozido, 0 = runtime                      */
} LxSpriteSrc;

int lx_suzy_sprite_source(const LxScb *scb, LxSpriteSrc *out);

/* Resolve a paleta efetiva: pens do SCB -> índices Mikey -> RGB555. Cache por
 * (pen map, época da paleta Mikey). Devolve 16 entradas RGB555 estáveis até
 * o fim do frame. */
const lx_u16 *lx_suzy_resolve_plut(const lx_u8 pen[8]);

/* ===== 4. SCB -> Cel =============================================================== */
LxMapQuality lx_suzy_scb_to_cel(const LxScb *scb, const LxSpriteSrc *src,
                                const LxViewXform *vx, LxCelDesc *out);

/* ===== 5. Execução do motor de sprites ================================================= */

/* Chamada ao escrever SPRGO. Percorre a cadeia a partir de lx_suzy.scbnext até
 * o terminador. Em LX_SCHED_DEFERRED apenas enfileira; em LX_SCHED_IMMEDIATE
 * submete já. Em ambos, marca SPRSYS busy e debita ao relógio do Lynx o custo
 * estimado do desenho (jogos fazem polling de busy e a CPU real ficava parada). */
void lx_suzy_sprgo(void);

/* Pontos de sincronismo em que a fila DEVE ser descarregada (DrawCels):
 *   - flip de buffer (Mikey DISPADR) ou vblank
 *   - leitura da lx_ram na faixa do framebuffer (LX_FB_UNDER/LX_FB_SOFT)
 *   - mudança de VIDBASE para outra superfície
 *   - leitura de SPRSYS sem busy esperado (polling) quando a fila é longa */
void lx_suzy_flush(void);

/* Início de frame: zera filas, época de PLUT, contadores. */
void lx_suzy_frame_begin(void);

/* Estatísticas de diagnóstico (LX_DEBUG): quantos sprites por LxMapQuality. */
typedef struct LxSuzyStats {
    lx_u32 sprites[4];          /* indexado por LxMapQuality                        */
    lx_u32 cook_hits, cook_misses, plut_misses;
} LxSuzyStats;
const LxSuzyStats *lx_suzy_stats(void);

/* ===== 6. Colisão (software; o Cel Engine não tem equivalente) ======================= */
/* O Suzy grava, durante o desenho, o número de colisão no "depósito" do SCB; o
 * jogo lê isso depois. LX_COLL_BBOX: interseção de retângulos no momento do
 * enfileiramento. LX_COLL_PIXEL: máscara por pixel em software, só para
 * sprites cujo tipo tem colisão. */
void lx_suzy_coll_begin_frame(void);
void lx_suzy_coll_record(const LxScb *scb, const LxCelDesc *cel);
/* escreve no depósito do SCB (lx_ram) o maior número de colisão encontrado */
void lx_suzy_coll_commit(const LxScb *scb);

/* ===== 7. Matemática do Suzy (NÃO é Cel; ARM60 tem MUL, mas não tem divisão) ============ */
/* Disparada por escrita nos registradores de maior ordem (MATHA/MATHE...).
 * Resultado fiel (inclui sinal, acumulação e flags de erro/overflow em SPRSYS). */
void lx_suzy_math_on_write(lx_u32 addr, lx_u8 val);
lx_u8 lx_suzy_math_read(lx_u32 addr);
int   lx_suzy_math_busy(void);     /* 0 imediatamente (resultado instantâneo)  */

#endif /* LX_SUZY_H */
