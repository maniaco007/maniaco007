/* test_video.c — paleta, expansão de cor e DMA de vídeo do Mikey (host, C89). */
#include <stdio.h>
#include "lynx/lx_video.h"

static int fails;
#define CHECK(c) do { if (!(c)) { printf("FALHA linha %d: %s\n", __LINE__, #c); fails++; } } while (0)

int main(void)
{
    lx_u16 plut[LX_PALETTE_SIZE];
    unsigned i;
    lx_u8 v;

    lx_video_reset();
    CHECK(lx_video_rgb555(0) == 0);                                   /* tudo zero = preto */

    /* GREEN usa o nibble baixo; BLUERED: azul = nibble alto, vermelho = baixo (Handy) */
    lx_video_write(LX_REG_GREEN0 + 3, 0xF7);                          /* lixo no nibble alto deve ser ignorado */
    lx_video_write(LX_REG_BLUERED0 + 3, 0xA5);                        /* azul=A, vermelho=5 */
    CHECK(lx_video_rgb555(3) == (lx_u16)((((5 << 1) | (5 >> 3)) << 10) | (((7 << 1) | (7 >> 3)) << 5) | ((10 << 1) | (10 >> 3))));
    CHECK(lx_video_read(LX_REG_GREEN0 + 3, &v) && v == 0x07);

    /* $F nos três componentes = branco total (31,31,31) */
    lx_video_write(LX_REG_GREEN0 + 15, 0x0F);
    lx_video_write(LX_REG_BLUERED0 + 15, 0xFF);
    CHECK(lx_video_rgb555(15) == 0x7FFF);
    CHECK(lx_video_rgb555(15 + 16) == 0x7FFF);                        /* pen é mascarado em 4 bits */

    /* vermelho puro e azul puro (R nos bits 14-10, B nos 4-0) */
    lx_video_write(LX_REG_GREEN0 + 1, 0x00);
    lx_video_write(LX_REG_BLUERED0 + 1, 0x0F);
    CHECK(lx_video_rgb555(1) == (31u << 10));
    lx_video_write(LX_REG_BLUERED0 + 2, 0xF0);
    CHECK(lx_video_rgb555(2) == 31u);

    /* PLUT inteira coerente com o pen a pen */
    lx_video_plut(plut);
    for (i = 0; i < LX_PALETTE_SIZE; i++) CHECK(plut[i] == lx_video_rgb555(i));

    /* DISPADR L/H e DISPCTL */
    lx_video_write(LX_REG_DISPADRL, 0x34);
    lx_video_write(LX_REG_DISPADRH, 0xC0);
    CHECK(lx_video_dispadr() == 0xC034UL);
    lx_video_write(LX_REG_DISPADRL, 0x00);
    CHECK(lx_video_dispadr() == 0xC000UL);                            /* escrever L não pode zerar H */
    CHECK(!lx_video_dma_enabled());
    lx_video_write(LX_REG_DISPCTL, 0x09);
    CHECK(lx_video_dma_enabled() && lx_video_dispctl() == 0x09);

    /* endereços que não são de vídeo não são tratados */
    CHECK(lx_video_write(0xFD00, 1) == 0);
    CHECK(lx_video_read(0xFC91, &v) == 0);

    /* época da paleta só muda em escrita de paleta */
    {
        lx_u32 e0 = lx_video_palette_epoch();
        lx_video_write(LX_REG_DISPADRL, 1);
        CHECK(lx_video_palette_epoch() == e0);
        lx_video_write(LX_REG_GREEN0, 1);
        CHECK(lx_video_palette_epoch() != e0);
    }

    if (fails) { printf("test_video: %d falha(s)\n", fails); return 1; }
    printf("test_video: OK\n");
    return 0;
}
