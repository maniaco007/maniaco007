/*
 * lx_cel.h — descritor de Cel NEUTRO de plataforma.
 *
 * Este é o "idioma intermediário" entre o HLE do Suzy (que entende SCBs do
 * Lynx) e o backend gráfico (que entende CCBs do 3DO, ou um rasterizador de
 * software no host). O HLE nunca inclui headers do SDK 3DO.
 *
 * Correspondência com o CCB do 3DO (nomes de campos do SDK entre colchetes).
 * Formatos de ponto-fixo conforme a documentação do CCB — [VERIFY] contra o
 * SDK (não disponível neste ambiente):
 *   xpos,ypos : 16.16   [ccb_XPos, ccb_YPos]   posição do canto de origem
 *   hdx,hdy   : 12.20   [ccb_HDX, ccb_HDY]     passo na direção de uma linha da fonte
 *   vdx,vdy   : 16.16   [ccb_VDX, ccb_VDY]     passo entre linhas da fonte
 *   hddx,hddy : 12.20   [ccb_HDDX, ccb_HDDY]   variação do (hdx,hdy) por linha
 *                                              (perspectiva = STRETCH do Lynx)
 */
#ifndef LX_CEL_H
#define LX_CEL_H

#include "lx_types.h"
#include "lx_config.h"

#define LX_FIX16(i)   ((lx_fix16)((lx_s32)(i) << 16))
#define LX_FIX20(i)   ((lx_fix20)((lx_s32)(i) << 20))

/* Formato dos pixels já "cozidos" para o Cel Engine */
#define LX_PIX_CODED4_PACKED    0   /* 4bpp indexado, RLE no formato "packed" do 3DO (padrão: economiza RAM) */
#define LX_PIX_CODED4_UNPACKED  1   /* 4bpp indexado, linhas alinhadas em 32 bits                           */
#define LX_PIX_CODED8_UNPACKED  2   /* reservado                                                            */

/* Modos de composição (backend traduz para PIXC/flags do CCB) */
#define LX_BLEND_OPAQUE         0   /* pen 0 também desenha (tipos BACKGROUND*)  */
#define LX_BLEND_KEY0           1   /* pen 0 transparente (NORMAL/BOUNDARY/...)  */
#define LX_BLEND_SHADOW         2   /* sombra: escurece o fundo (aprox.)         */

/* flags de LxCelDesc.flags */
#define LX_CELF_LAST        0x0001  /* último Cel da cadeia                        */
#define LX_CELF_FALLBACK    0x0002  /* NÃO mapeável: rasterizar em software (XOR etc.) */
#define LX_CELF_HAS_COLL    0x0004  /* participa da colisão (ver lx_suzy.h)         */
#define LX_CELF_RUNTIME_PIX 0x0008  /* pixels convertidos em runtime (não pré-cozidos) */

typedef struct LxCelDesc {
    lx_u32      flags;              /* LX_CELF_*                                   */
    const void *pixels;             /* dados do Cel, alinhados em 32 bits          */
    const lx_u16 *plut;             /* 16 entradas RGB555 já resolvidas (pen->cor) */
    lx_fix16    xpos, ypos;
    lx_fix20    hdx, hdy, hddx, hddy;
    lx_fix16    vdx, vdy;
    lx_u16      width, height;      /* da fonte, em pixels                          */
    lx_u8       pix_format;         /* LX_PIX_*                                     */
    lx_u8       blend;              /* LX_BLEND_*                                   */
    lx_u8       surface;            /* índice de LxSurface destino (VIDBASE)         */
    lx_u8       sprite_type;        /* LX_SPR_* original (colisão/diagnóstico)      */
    lx_u16      scb_addr;           /* SCB de origem (debug, depósito de colisão)    */
    lx_u16      coll_id;            /* número de colisão do SCB (SPRCOLL b3-b0)      */
} LxCelDesc;

/* Qualidade do mapeamento SCB -> Cel (relatada por lx_suzy_scb_to_cel) */
typedef enum LxMapQuality {
    LX_MAP_NATIVE = 0,      /* equivalente exato no Cel Engine                      */
    LX_MAP_APPROX,          /* aproximação aceita (ex.: SHADOW, TILT em flips)      */
    LX_MAP_FALLBACK_SOFT,   /* não mapeável: usar rasterizador de software          */
    LX_MAP_SKIP             /* sprite com SKIP / tamanho zero: nada a desenhar      */
} LxMapQuality;

/* Transformação global de visualização: escala 2x + letterbox + rotação do
 * cabeçalho .lnx, composta UMA vez e aplicada a todo Cel (2x2 em 16.16 + translação). */
typedef struct LxViewXform {
    lx_fix16 m00, m01, m10, m11;    /* [x'] = [m00 m01][x] + [tx]                    */
    lx_fix16 tx, ty;                /* [y']   [m10 m11][y]   [ty]                    */
} LxViewXform;

void lx_view_init(LxViewXform *vx, lx_u8 cart_rotation);

#endif /* LX_CEL_H */
