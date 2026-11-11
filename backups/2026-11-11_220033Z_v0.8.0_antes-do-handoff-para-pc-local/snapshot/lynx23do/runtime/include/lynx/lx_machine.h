/*
 * lx_machine.h — a "máquina Lynx" em execução: CPU, RAM, agendador de quadros, vídeo e registradores mínimos.
 * Independente de plataforma: o laço principal de cada plataforma (3DO, host) chama lx_machine_run_frame() e
 * depois lx_machine_present().
 *
 * ESTADO (M1): o quadro é cronometrado por contagem de ciclos (66 667 ciclos de 4 MHz ~ 60 Hz). AINDA NÃO existem:
 * timers/IRQ do Mikey, vblank por interrupção, áudio, Suzy (sprites, matemática, colisão), cartucho serial.
 * Programas que dependem disso (a maioria dos jogos) ainda não funcionam; homebrew que desenha por CPU e faz
 * polling funciona. Escritas em SPRGO são CONTADAS (lx_suzy_min_sprgo_ignored) e ignoradas.
 */
#ifndef LX_MACHINE_H
#define LX_MACHINE_H

#include "lx_types.h"
#include "lx_config.h"
#include "lx_cpu_abi.h"
#include "lx_overlay.h"

#define LX_CYCLES_PER_FRAME 66667UL

extern LxCpu lx_cpu;
extern lx_u32 lx_suzy_min_sprgo_ignored;

/* Zera a RAM, copia 'image' para lx_ram[load_addr..], ativa o overlay 'ov' e prepara a CPU em 'entry'. 0 = ok. */
int  lx_machine_init(const lx_u8 *image, lx_u32 image_size, lx_u32 load_addr, const LxOverlay *ov, lx_u32 entry);

/* Executa até o fim do quadro (YIELD do agendador). 0 = ok, 1 = parou (PC sem tradução ou STP). */
int  lx_machine_run_frame(void);

/* Entrega o quadro à plataforma: paleta -> PLUT, framebuffer da RAM Lynx -> camada de fundo, apresenta. */
void lx_machine_present(void);

lx_u32 lx_machine_frames(void);
lx_u32 lx_machine_pc(void);

#endif /* LX_MACHINE_H */
