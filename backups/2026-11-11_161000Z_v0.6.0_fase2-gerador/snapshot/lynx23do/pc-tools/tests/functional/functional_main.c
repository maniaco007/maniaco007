/*
 * functional_main.c — executa uma IMAGEM FLAT de 64 KB (ex.: suíte funcional de Klaus Dormann) traduzida
 * pelo lynx2c, com o trampolim real (lx_run/lx_dispatch/lx_overlay).
 *
 * Uso: functional_harness <imagem.bin> <entrada_hex> <max_ciclos> [chunk]
 * Saída (uma linha): 
 *   TRAP pc=$XXXX cycles=N A=.. X=.. Y=.. S=.. P=..   (laço no PC: sucesso OU falha, decide o chamador)
 *   UNRESOLVED pc=$XXXX                               (sem código traduzido: o chamador adiciona seed)
 *   TIMEOUT pc=$XXXX cycles=N
 * Código de saída: 0 = TRAP, 3 = UNRESOLVED, 4 = TIMEOUT, 2 = erro de uso.
 *
 * Trap = o mesmo PC, os mesmos registradores E a RAM inteira idêntica (hash FNV-1a de 64 KB) em 3 YIELDs
 * consecutivos. Só PC+registradores dava FALSO POSITIVO na fase 2: os pontos de retomada ficam restritos a
 * instruções de fluxo, então um laço longo que muda só a RAM (o teste decimal) cedia sempre no mesmo PC.
 * A imagem inteira é copiada para a RAM do Lynx: código e dados convivem na mesma RAM.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "lynx/lx_cpu_abi.h"
#include "lynx/lx_mem.h"
#include "lynx/lx_overlay.h"

extern const LxOverlay lx_ov0;
extern lx_u32 lx_t_yield_pc;
/* Hooks HLE de "pular trecho": a rotina em SKIPi_FROM é substituída por um salto para SKIPi_TO
 * (política "hook" do docs/02 §6 para código auto-modificável). Definidos com -DSKIPi_FROM/-DSKIPi_TO. */
#ifdef SKIP0_FROM
static lx_u32 skip0(LxCpu *c) { (void)c; return SKIP0_TO; }
#endif
#ifdef SKIP1_FROM
static lx_u32 skip1(LxCpu *c) { (void)c; return SKIP1_TO; }
#endif
#ifdef SKIP2_FROM
static lx_u32 skip2(LxCpu *c) { (void)c; return SKIP2_TO; }
#endif
#ifdef SKIP3_FROM
static lx_u32 skip3(LxCpu *c) { (void)c; return SKIP3_TO; }
#endif
static const LxHook g_hooks[] = {
#ifdef SKIP0_FROM
    { 0xFFFF, SKIP0_FROM, skip0, "skip0" },
#endif
#ifdef SKIP1_FROM
    { 0xFFFF, SKIP1_FROM, skip1, "skip1" },
#endif
#ifdef SKIP2_FROM
    { 0xFFFF, SKIP2_FROM, skip2, "skip2" },
#endif
#ifdef SKIP3_FROM
    { 0xFFFF, SKIP3_FROM, skip3, "skip3" },
#endif
    { 0xFFFF, 0, 0, "sentinela" }      /* nao contada em n_hooks (evita inicializador vazio em C89) */
};
const LxProgram lx_program = { "funcional", LX_ABI_VERSION, 0, 0, 0,
                               (lx_u16)(sizeof g_hooks / sizeof g_hooks[0] - 1), g_hooks, 0 };

int main(int argc, char **argv)
{
    FILE *f;
    size_t n;
    LxCpu cpu;
    lx_u32 pc, entry, max_cycles, chunk = 100003UL, last_pc = 0xFFFFFFFFUL;
    unsigned same = 0;
    lx_u8 last[5] = { 0, 0, 0, 0, 0 };
    lx_u32 last_hash = 0;

    if (argc < 4) { fprintf(stderr, "uso: %s imagem.bin entrada_hex max_ciclos [chunk]\n", argv[0]); return 2; }
    f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 2; }
    n = fread(lx_ram, 1, LX_RAM_SIZE, f);
    fclose(f);
    if (n == 0) { fprintf(stderr, "imagem vazia\n"); return 2; }
    entry = (lx_u32)strtoul(argv[2], 0, 16);
    max_cycles = (lx_u32)strtoul(argv[3], 0, 10);
    if (argc > 4) chunk = (lx_u32)strtoul(argv[4], 0, 10);

    lx_overlay_reset();
    lx_overlay_activate(&lx_ov0);
    memset(&cpu, 0, sizeof cpu);
    cpu.s = 0xFF;
    cpu.i = 1;
    pc = entry;

    for (;;) {
        lx_u32 r;
        cpu.next_event = cpu.cycles + chunk;
        r = lx_run(&cpu, pc);
        if (r == LX_PC_HALT) {
            printf("UNRESOLVED pc=$%04lX\n", (unsigned long)lx_unresolved_pc);
            return 3;
        }
        pc = lx_t_yield_pc;
        {
            lx_u8 now[5];
            lx_u32 h = 2166136261UL;
            unsigned long k;
            now[0] = cpu.a; now[1] = cpu.x; now[2] = cpu.y; now[3] = cpu.s; now[4] = lx_cpu_pack_p(&cpu);
            for (k = 0; k < LX_RAM_SIZE; k++) h = (h ^ lx_ram[k]) * 16777619UL;
            if (pc == last_pc && memcmp(now, last, 5) == 0 && h == last_hash) same++; else same = 0;
            memcpy(last, now, 5);
            last_hash = h;
            last_pc = pc;
            if (same >= 2) {
                printf("TRAP pc=$%04lX cycles=%lu A=%02X X=%02X Y=%02X S=%02X P=%02X\n", (unsigned long)pc,
                       (unsigned long)cpu.cycles, now[0], now[1], now[2], now[3], now[4]);
                return 0;
            }
        }
        if (cpu.cycles > max_cycles) {
            printf("TIMEOUT pc=$%04lX cycles=%lu\n", (unsigned long)pc, (unsigned long)cpu.cycles);
            return 4;
        }
    }
}
