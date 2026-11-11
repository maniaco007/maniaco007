/*
 * main_prog.c — executa programs.bin: código gerado + trampolim REAL (lx_run/lx_dispatch/lx_overlay).
 * Uso: harness_prog programs.bin      (exit 0 = todos os vetores iguais ao oráculo)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "lynx/lx_cpu_abi.h"
#include "lynx/lx_mem.h"
#include "lynx/lx_overlay.h"

extern const LxOverlay *const lx_test_ovs[];
extern const unsigned lx_test_novs;
extern unsigned lx_t_io_n, lx_t_io_overflow, lx_t_misroute;
extern lx_u32 lx_t_io_addr[];
extern lx_u8  lx_t_io_val[];
extern lx_u32 lx_t_yield_pc;

/* LxProgram mínimo exigido por lx_overlay.c (sem hooks); o gerador real emite o verdadeiro */
const LxProgram lx_program = { "teste", LX_ABI_VERSION, 0, 0, 0, 0, 0, 0 };

static const unsigned char *g_buf;
static unsigned long g_len, g_pos;

static unsigned rd8(void)
{
    if (g_pos + 1 > g_len) { fprintf(stderr, "programs.bin truncado\n"); exit(2); }
    return g_buf[g_pos++];
}
static unsigned rd16(void) { unsigned lo = rd8(); return lo | (rd8() << 8); }
static lx_u32 rd32(void) { lx_u32 lo = rd16(); return lo | ((lx_u32)rd16() << 16); }

#define MAX_TOUCH 8192
#define MAX_W 4096
static unsigned touch[MAX_TOUCH];
static unsigned w_addr[MAX_W], w_val[MAX_W], io_addr[LX_RAM_SIZE > 0 ? 1024 : 1], io_val[1024];

int main(int argc, char **argv)
{
    FILE *f;
    unsigned long n, i, fails = 0, stray = 0, nyield = 0, nunres = 0;
    unsigned shown = 0;

    if (argc < 2) { fprintf(stderr, "uso: %s programs.bin\n", argv[0]); return 2; }
    f = fopen(argv[1], "rb");
    if (!f) { perror("programs.bin"); return 2; }
    fseek(f, 0, SEEK_END); g_len = (unsigned long)ftell(f); fseek(f, 0, SEEK_SET);
    g_buf = (const unsigned char *)malloc(g_len);
    if (!g_buf || fread((void *)g_buf, 1, g_len, f) != g_len) { fprintf(stderr, "leitura falhou\n"); return 2; }
    fclose(f);
    if (memcmp(g_buf, "LXV2", 4) != 0) { fprintf(stderr, "magic inválido\n"); return 2; }
    g_pos = 4;
    n = rd32();

    for (i = 0; i < n; i++) {
        LxCpu cpu;
        unsigned prog, ia, ix, iy, is, ip, entry, ns, k, nt = 0, ok = 1;
        unsigned reason, stop_pc, ea, ex, ey, es, ep, pmask, nw, nio;
        lx_u32 budget, ecyc, ret;
        const char *why = "";

        prog = rd16();
        ia = rd8(); ix = rd8(); iy = rd8(); is = rd8(); ip = rd8();
        entry = rd16();
        budget = rd32();
        ns = rd16();
        for (k = 0; k < ns; k++) {
            unsigned a = rd16(), v = rd8();
            if (nt < MAX_TOUCH) touch[nt++] = a;
            lx_ram[a] = (lx_u8)v;
        }
        reason = rd8(); stop_pc = rd16();
        ea = rd8(); ex = rd8(); ey = rd8(); es = rd8(); ep = rd8(); pmask = rd8();
        ecyc = rd32();
        nw = rd16();
        if (nw > MAX_W) { fprintf(stderr, "escritas demais\n"); return 2; }
        for (k = 0; k < nw; k++) { w_addr[k] = rd16(); w_val[k] = rd8(); if (nt < MAX_TOUCH) touch[nt++] = w_addr[k]; }
        nio = rd16();
        if (nio > 1024) { fprintf(stderr, "E/S demais\n"); return 2; }
        for (k = 0; k < nio; k++) { io_addr[k] = rd16(); io_val[k] = rd8(); }

        if (prog >= lx_test_novs) { fprintf(stderr, "prog %u inexistente\n", prog); return 2; }
        lx_overlay_reset();
        lx_overlay_activate(lx_test_ovs[prog]);

        memset(&cpu, 0, sizeof cpu);
        cpu.a = (lx_u8)ia; cpu.x = (lx_u8)ix; cpu.y = (lx_u8)iy; cpu.s = (lx_u8)is;
        lx_cpu_unpack_p(&cpu, (lx_u8)ip);
        cpu.next_event = budget;
        lx_t_io_n = 0; lx_t_misroute = 0; lx_t_io_overflow = 0;
        lx_t_yield_pc = 0xFFFFFFFFUL;
        lx_unresolved_pc = 0xFFFFFFFFUL;

        ret = lx_run(&cpu, entry);

        if (lx_t_misroute) { ok = 0; why = "E/S roteada ao chip errado"; }
        else if (reason == 0 && (ret != LX_PC_YIELD || lx_t_yield_pc != stop_pc || lx_unresolved_pc != 0xFFFFFFFFUL))
            { ok = 0; why = "parada: esperado YIELD no PC"; }
        else if (reason == 1 && (ret != LX_PC_HALT || lx_unresolved_pc != stop_pc || lx_t_yield_pc != 0xFFFFFFFFUL))
            { ok = 0; why = "parada: esperado PC nao resolvido"; }
        else if (cpu.a != ea || cpu.x != ex || cpu.y != ey || cpu.s != es) { ok = 0; why = "registradores"; }
        else if ((lx_cpu_pack_p(&cpu) & pmask) != (ep & pmask)) { ok = 0; why = "flags(P) vivos"; }
        else if (cpu.cycles != ecyc) { ok = 0; why = "ciclos"; }
        else if (lx_t_io_n != nio || lx_t_io_overflow) { ok = 0; why = "n escritas E/S"; }
        else {
            for (k = 0; k < nio; k++)
                if (lx_t_io_addr[k] != io_addr[k] || lx_t_io_val[k] != io_val[k]) { ok = 0; why = "escrita E/S"; break; }
            for (k = 0; ok && k < nw; k++)
                if (lx_ram[w_addr[k]] != w_val[k]) { ok = 0; why = "escrita RAM"; }
        }
        if (reason == 0) nyield++; else nunres++;

        if (!ok) {
            fails++;
            if (shown++ < 15)
                printf("FALHA vetor %lu prog=%u (%s) entry=$%04X budget=%lu: in A=%02X X=%02X Y=%02X S=%02X P=%02X | "
                       "esperado %s $%04X A=%02X X=%02X Y=%02X S=%02X P=%02X cyc=%lu | obtido r=%lX A=%02X X=%02X Y=%02X S=%02X P=%02X cyc=%lu yield=$%lX unres=$%lX\n",
                       i, prog, why, entry, (unsigned long)budget, ia, ix, iy, is, ip,
                       reason ? "UNRES" : "YIELD", stop_pc, ea, ex, ey, es, ep, (unsigned long)ecyc,
                       (unsigned long)ret, cpu.a, cpu.x, cpu.y, cpu.s, lx_cpu_pack_p(&cpu), (unsigned long)cpu.cycles,
                       (unsigned long)lx_t_yield_pc, (unsigned long)lx_unresolved_pc);
        }
        for (k = 0; k < nt; k++) lx_ram[touch[k]] = 0;
        for (k = 0; k < 0x200; k++) lx_ram[0x100 + (k & 0xFF)] = 0;          /* pilha: tocada por JSR/RTS */
        if ((i & 63) == 0) {
            unsigned long a;
            for (a = 0; a < LX_RAM_SIZE; a++)
                if (lx_ram[a]) { stray++; if (shown++ < 15) printf("ESCRITA ESTRANHA em $%04lX (vetor %lu)\n", a, i); lx_ram[a] = 0; }
        }
    }
    printf("vetores: %lu (yield %lu, nao-resolvido %lu)  falhas: %lu  escritas estranhas: %lu  programas: %u\n",
           n, nyield, nunres, fails, stray, lx_test_novs);
    return (fails || stray) ? 1 : 0;
}
