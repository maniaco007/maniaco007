/*
 * lx_platform_host.c — backend de PC (sem tela): implementa lx_platform.h e grava o quadro como PPM.
 * Serve de teste de ponta a ponta no host (tradutor -> runtime -> Mikey -> paleta -> framebuffer -> imagem).
 */
#include <stdio.h>
#include <string.h>

#include "lynx/lx_platform.h"
#include "lynx/lx_config.h"

lx_u8 lx_host_joystick;                 /* definido pelo main de teste */
lx_u8 lx_host_switches;
lx_u32 lx_host_ignored_cels;
const char *lx_host_dump_path;          /* se não nulo, present() grava o PPM do quadro (sobrescreve) */
lx_u32 lx_host_dump_frame = 0xFFFFFFFFUL;

static lx_u16 g_plut[LX_PALETTE_SIZE];
static const lx_u8 *g_fb;
static lx_u32 g_frame;

int  lx_gfx_init(void)     { g_fb = 0; g_frame = 0; return 0; }
void lx_gfx_shutdown(void) {}
int  lx_gfx_surface_bind(lx_u8 surface, lx_u16 lynx_vidbase) { (void)surface; (void)lynx_vidbase; return 0; }

void lx_gfx_set_palette(const lx_u16 rgb555[LX_PALETTE_SIZE]) { memcpy(g_plut, rgb555, sizeof g_plut); }

void lx_gfx_submit_cels(const LxCelDesc *cels, lx_u32 n) { (void)cels; lx_host_ignored_cels += n; }
void lx_gfx_submit_fb_layer(const lx_u8 *lynx_fb, lx_u8 surface) { (void)surface; g_fb = lynx_fb; }

static void dump_ppm(const char *path)
{
    FILE *f = fopen(path, "wb");
    int x, y;
    if (!f) return;
    fprintf(f, "P6\n%d %d\n255\n", LX_SCREEN_W, LX_SCREEN_H);
    for (y = 0; y < LX_SCREEN_H; y++) {
        for (x = 0; x < LX_SCREEN_W; x++) {
            lx_u8 b = g_fb ? g_fb[y * LX_FB_BYTES_PER_LINE + (x >> 1)] : 0;
            unsigned pen = (x & 1) ? (b & 0x0F) : (b >> 4);              /* esquerda = nibble ALTO */
            lx_u16 c = g_fb ? g_plut[pen] : 0;                           /* sem camada de fundo (DMA desligado): preto */
            unsigned r5 = (c >> 10) & 31, g5 = (c >> 5) & 31, b5 = c & 31;
            fputc((r5 << 3) | (r5 >> 2), f);
            fputc((g5 << 3) | (g5 >> 2), f);
            fputc((b5 << 3) | (b5 >> 2), f);
        }
    }
    fclose(f);
}

void lx_gfx_present(lx_u8 surface)
{
    (void)surface;
    if (lx_host_dump_path && g_frame == lx_host_dump_frame) dump_ppm(lx_host_dump_path);
    g_frame++;
    g_fb = 0;                    /* a camada de fundo vale só para o quadro em que foi enviada (como no backend 3DO) */
}

lx_u8  lx_input_joystick(void) { return lx_host_joystick; }
lx_u8  lx_input_switches(void) { return lx_host_switches; }
lx_u32 lx_time_ms(void)        { return g_frame * 16UL; }

const lx_u8 *lx_file_load(const char *path, lx_u32 *out_size)
{
    static lx_u8 buf[1 << 20];
    FILE *f = fopen(path, "rb");
    size_t n;
    if (!f) return 0;
    n = fread(buf, 1, sizeof buf, f);
    fclose(f);
    *out_size = (lx_u32)n;
    return buf;
}
