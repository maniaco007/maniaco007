/*
 * lx_config.h — constantes da máquina-alvo (Lynx) e opções de build do runtime.
 *
 * Opções podem ser sobrescritas na linha de comando (-DLX_...=...) ou pelo
 * lynx2c, que gera "lx_game_config.h" a partir do manifest do jogo.
 */
#ifndef LX_CONFIG_H
#define LX_CONFIG_H

/* ---- Plataforma de destino (definir exatamente UMA) ---------------------- */
/*   LX_TARGET_3DO  : armcc + SDK Portfolio; backend gráfico = DrawCels()      */
/*   LX_TARGET_HOST : gcc/clang no PC; backend = rasterizador de software      */
#if !defined(LX_TARGET_3DO) && !defined(LX_TARGET_HOST)
#  define LX_TARGET_HOST 1
#endif
#if defined(LX_TARGET_3DO) && defined(LX_TARGET_HOST)
#  error "Defina apenas um de LX_TARGET_3DO / LX_TARGET_HOST"
#endif

/* ---- Fatos do Lynx --------------------------------------------------------- */
#define LX_RAM_SIZE        65536UL
#define LX_CPU_HZ          4000000UL   /* 65C02 @ 4 MHz (relógio de referência dos ciclos) */
#define LX_SCREEN_W        160
#define LX_SCREEN_H        102
#define LX_FB_BYTES_PER_LINE 80        /* 160 px * 4 bpp / 8 */
#define LX_FB_BYTES        (LX_FB_BYTES_PER_LINE * LX_SCREEN_H)   /* 8160 */
#define LX_PALETTE_SIZE    16          /* 16 cores de 12 bits (Mikey GREEN/BLUERED) */

/* ---- Saída de vídeo no 3DO ------------------------------------------------- */
#ifndef LX_VIEW_SCALE
#  define LX_VIEW_SCALE    2           /* fator inteiro: 160x102 -> 320x204 */
#endif
#ifndef LX_VIEW_W
#  define LX_VIEW_W        320
#endif
#ifndef LX_VIEW_H
#  define LX_VIEW_H        240
#endif

/* ---- Modos de operação (padrões; o manifest do jogo sobrescreve) ----------- */
/* Modo de framebuffer: ver docs/03-hle-suzy.md §5                              */
#define LX_FB_CEL_ONLY     0   /* sprites -> Cels; escritas de CPU no fb ignoradas   */
#define LX_FB_UNDER        1   /* fb da RAM Lynx vira Cel de fundo + Cels por cima   */
#define LX_FB_SOFT         2   /* Suzy em software p/ lx_ram (preciso, lento)         */
#ifndef LX_FB_MODE
#  define LX_FB_MODE       LX_FB_CEL_ONLY
#endif

/* Colisão: ver docs/03-hle-suzy.md §6 */
#define LX_COLL_NONE       0
#define LX_COLL_BBOX       1   /* retângulos envolventes */
#define LX_COLL_PIXEL      2   /* máscara por pixel em software */
#ifndef LX_COLL_MODE
#  define LX_COLL_MODE     LX_COLL_BBOX
#endif

/* Agendamento do desenho: ver docs/03-hle-suzy.md §4 */
#define LX_SCHED_IMMEDIATE 0   /* DrawCels a cada SPRGO */
#define LX_SCHED_DEFERRED  1   /* acumula; submete no flip/vblank ou ponto de sincronismo */
#ifndef LX_SPRITE_SCHED
#  define LX_SPRITE_SCHED  LX_SCHED_DEFERRED
#endif

/* ---- Limites estáticos (sem malloc em loop quente) ------------------------- */
#ifndef LX_MAX_CELS_PER_FRAME
#  define LX_MAX_CELS_PER_FRAME  256
#endif
#ifndef LX_MAX_PLUTS
#  define LX_MAX_PLUTS           64    /* cache de paletas por (penmap, época de paleta) */
#endif
#ifndef LX_MAX_OVERLAYS
#  define LX_MAX_OVERLAYS        32
#endif
#ifndef LX_MAX_SURFACES
#  define LX_MAX_SURFACES        3     /* buffers de vídeo Lynx distintos (VIDBASE) */
#endif
#ifndef LX_MAX_HOOKS
#  define LX_MAX_HOOKS           64
#endif

/* ---- Diagnóstico ------------------------------------------------------------ */
#ifndef LX_DEBUG
#  define LX_DEBUG 0     /* 1: asserts, log de PCs não resolvidos, contadores */
#endif

#endif /* LX_CONFIG_H */
