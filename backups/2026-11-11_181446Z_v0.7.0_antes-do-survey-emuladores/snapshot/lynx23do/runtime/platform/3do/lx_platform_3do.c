/*
 * lx_platform_3do.c — backend 3DO (Portfolio/Opera) de lx_platform.h.
 *
 * Chamadas e constantes conferidas nos headers REAIS do SDK (trapexit/3do-devkit, include/3do): OpenGraphicsFolio,
 * InitEventUtility, CreateBasicDisplay, GetVBLIOReq, GetTimerIOReq, CreateCel, CreateBackdropCel, DrawScreenCels,
 * DisplayScreen, WaitVBL, GetControlPad, OpenDiskStream/ReadDiskStream. A sequência de inicialização e de quadro
 * (dois buffers, DrawScreenCels -> DisplayScreen -> WaitVBL, formatos de ponto fixo do CCB) segue o exemplo funcional
 * XProger/nes-3do (BSD-2-Clause; ver NOTICE.md).
 *
 * ESTADO: escrito contra os headers, AINDA NÃO COMPILADO COM O armcc NEM EXECUTADO em emulador ou hardware.
 * Implementa o suficiente para o marco M1/M2 (framebuffer do Lynx como Cel de tela cheia, controle, tempo, arquivo).
 * lx_gfx_submit_cels (sprites SCB->Cel) é M3 e hoje só conta o que ignora.
 */
#include "types.h"
#include "mem.h"
#include "graphics.h"
#include "displayutils.h"
#include "celutils.h"
#include "event.h"
#include "controlpad.h"
#include "timerutils.h"
#include "filestream.h"
#include "filestreamfunctions.h"

#include "lynx/lx_platform.h"
#include "lynx/lx_config.h"

/* tela do 3DO e área onde o quadro do Lynx (160x102) é desenhado em 2x: 320x204, centrado verticalmente */
#define SCR_W   320
#define SCR_H   240
#define DST_W   (LX_SCREEN_W * LX_VIEW_SCALE)
#define DST_H   (LX_SCREEN_H * LX_VIEW_SCALE)

static ScreenContext g_ctx;
static Item g_vbl;
static Item g_timer;

static CCB *g_backdrop;                          /* preto, tela cheia: limpa o buffer a cada quadro */
static CCB *g_fb_cel;                            /* framebuffer 4 bpp do Lynx como Cel codificado */
static lx_u32 g_fb_words[LX_FB_BYTES / 4];       /* cópia ALINHADA a 32 bits (o Cel Engine exige) */
static lx_u16 g_plut[LX_PALETTE_SIZE];           /* PLUT: 16 entradas RGB555 */
static int g_have_fb;

static lx_u8 g_joy;                              /* estado do controle, amostrado UMA vez por quadro */
static lx_u8 g_switches;

lx_u32 lx_3do_ignored_cels;

int lx_gfx_init(void)
{
    if (OpenGraphicsFolio() < 0) return -1;
    if (InitEventUtility(1, 0, LC_Observer) < 0) return -1;
    if (CreateBasicDisplay(&g_ctx, DI_TYPE_DEFAULT, 2) < 0) return -1;

    g_vbl = GetVBLIOReq();
    g_timer = GetTimerIOReq();

    g_backdrop = CreateBackdropCel(SCR_W, SCR_H, 0, 100);
    if (!g_backdrop) return -1;

    g_fb_cel = CreateCel(LX_SCREEN_W, LX_SCREEN_H, 4, CREATECEL_CODED, g_fb_words);
    if (!g_fb_cel) return -1;
    g_fb_cel->ccb_PLUTPtr = g_plut;
    g_fb_cel->ccb_Flags |= (CCB_LDPLUT | CCB_PPABS | CCB_BGND | CCB_LAST);   /* pen 0 é uma cor de verdade no Lynx */
    g_fb_cel->ccb_NextPtr = NULL;
    g_fb_cel->ccb_HDX = LX_VIEW_SCALE << 20;                  /* 12.20 */
    g_fb_cel->ccb_VDY = LX_VIEW_SCALE << 16;                  /* 16.16 */
    g_fb_cel->ccb_XPos = ((SCR_W - DST_W) / 2) << 16;
    g_fb_cel->ccb_YPos = ((SCR_H - DST_H) / 2) << 16;
    return 0;
}

void lx_gfx_shutdown(void) {}

int lx_gfx_surface_bind(lx_u8 surface, lx_u16 lynx_vidbase)
{
    (void)surface; (void)lynx_vidbase;           /* uma só superfície lógica no M1/M2 */
    return 0;
}

void lx_gfx_set_palette(const lx_u16 rgb555[LX_PALETTE_SIZE])
{
    int i;
    for (i = 0; i < LX_PALETTE_SIZE; i++) g_plut[i] = rgb555[i];
}

void lx_gfx_submit_cels(const LxCelDesc *cels, lx_u32 n)
{
    (void)cels;
    lx_3do_ignored_cels += n;                    /* M3: SCB -> CCB ainda não implementado */
}

void lx_gfx_submit_fb_layer(const lx_u8 *lynx_fb, lx_u8 surface)
{
    lx_u32 i;
    lx_u8 *dst = (lx_u8 *)g_fb_words;
    (void)surface;
    for (i = 0; i < LX_FB_BYTES; i++) dst[i] = lynx_fb[i];     /* pixel da esquerda = nibble alto: igual ao 3DO */
    g_have_fb = 1;
}

static void poll_pad(void)
{
    ControlPadEventData ev;
    lx_u32 b;
    lx_u8 j = 0, s = 0;

    if (GetControlPad(1, 0, &ev) <= 0) return;                 /* sem evento novo: mantém o estado anterior */
    b = ev.cped_ButtonBits;
    /* JOYSTICK do Lynx ($FCB0): b7 Up, b6 Down, b5 Left, b4 Right, b3 Opção 1, b2 Opção 2, b1 Inside (B), b0 Outside (A) */
    if (b & ControlUp)    j |= 0x80;
    if (b & ControlDown)  j |= 0x40;
    if (b & ControlLeft)  j |= 0x20;
    if (b & ControlRight) j |= 0x10;
    if (b & ControlC)     j |= 0x08;
    if (b & ControlX)     j |= 0x04;
    if (b & ControlB)     j |= 0x02;
    if (b & ControlA)     j |= 0x01;
    if (b & ControlStart) s |= 0x01;                           /* SWITCHES ($FCB1) bit 0 = Pause */
    g_joy = j;
    g_switches = s;
}

void lx_gfx_present(lx_u8 surface)
{
    Item screen = g_ctx.sc_ScreenItems[g_ctx.sc_CurrentScreen];
    (void)surface;

    if (g_have_fb) {
        g_backdrop->ccb_Flags &= ~CCB_LAST;
        g_backdrop->ccb_NextPtr = g_fb_cel;
    } else {
        g_backdrop->ccb_Flags |= CCB_LAST;
        g_backdrop->ccb_NextPtr = NULL;
    }
    DrawScreenCels(screen, g_backdrop);
    DisplayScreen(screen, 0);
    g_ctx.sc_CurrentScreen ^= 1;
    WaitVBL(g_vbl, 1);                                         /* ~60 Hz */
    g_have_fb = 0;                                             /* a camada vale só para o quadro em que foi enviada */
    poll_pad();
}

lx_u8  lx_input_joystick(void) { return g_joy; }
lx_u8  lx_input_switches(void) { return g_switches; }
lx_u32 lx_time_ms(void)        { return (lx_u32)GetMSecTime(g_timer); }

const lx_u8 *lx_file_load(const char *path, lx_u32 *out_size)
{
    Stream *fs = OpenDiskStream((char *)path, 2048);
    void *buf;
    s32 size;

    if (!fs) return 0;
    size = fs->st_FileLength;
    buf = AllocMem(size, MEMTYPE_ANY);
    if (!buf || ReadDiskStream(fs, (char *)buf, size) < 0) {
        CloseDiskStream(fs);
        return 0;
    }
    CloseDiskStream(fs);
    *out_size = (lx_u32)size;
    return (const lx_u8 *)buf;
}
