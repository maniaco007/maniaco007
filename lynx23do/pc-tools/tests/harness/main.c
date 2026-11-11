/*
 * main.c — executa vectors.bin contra as funções C geradas pelo lynx2c.
 * Uso: harness vectors.bin      (exit 0 = todos os vetores iguais ao oráculo)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "lynx/lx_cpu_abi.h"
#include "lynx/lx_mem.h"

typedef lx_u32 (*LxTestFn)(LxCpu *cpu);
extern const LxTestFn lx_test_fns[];
extern const unsigned lx_test_nfns;
extern unsigned lx_t_io_n, lx_t_io_overflow, lx_t_misroute;
extern lx_u32 lx_t_io_addr[];
extern lx_u8  lx_t_io_val[];

static const unsigned char *g_buf;
static unsigned long g_len, g_pos;

static unsigned rd8(void)
{
    if (g_pos + 1 > g_len) { fprintf(stderr, "vectors.bin truncado\n"); exit(2); }
    return g_buf[g_pos++];
}
static unsigned rd16(void) { unsigned lo = rd8(); return lo | (rd8() << 8); }
static lx_u32 rd32(void) { lx_u32 lo = rd16(); return lo | ((lx_u32)rd16() << 16); }

#define MAX_TOUCH 512
static unsigned touch[MAX_TOUCH];

int main(int argc, char **argv)
{
    FILE *f;
    unsigned long n, i, fails = 0, stray = 0;
    unsigned shown = 0;
    static lx_u8 filebuf_dummy;

    (void)filebuf_dummy;
    if (argc < 2) { fprintf(stderr, "uso: %s vectors.bin\n", argv[0]); return 2; }
    f = fopen(argv[1], "rb");
    if (!f) { perror("vectors.bin"); return 2; }
    fseek(f, 0, SEEK_END); g_len = (unsigned long)ftell(f); fseek(f, 0, SEEK_SET);
    g_buf = (const unsigned char *)malloc(g_len);
    if (!g_buf || fread((void *)g_buf, 1, g_len, f) != g_len) { fprintf(stderr, "leitura falhou\n"); return 2; }
    fclose(f);
    if (memcmp(g_buf, "LXV1", 4) != 0) { fprintf(stderr, "magic inválido\n"); return 2; }
    g_pos = 4;
    n = rd32();

    for (i = 0; i < n; i++) {
        LxCpu cpu;
        unsigned fn, ia, ix, iy, is, ip, next_pc, ns, k, nt = 0, ok = 1;
        unsigned ea, ex, ey, es, ep, nw, nio;
        lx_u32 ecyc, ret;
        unsigned w_addr[64], w_val[64], io_addr[64], io_val[64];
        const char *why = "";

        fn = rd16();
        ia = rd8(); ix = rd8(); iy = rd8(); is = rd8(); ip = rd8();
        next_pc = rd16();
        ns = rd16();
        for (k = 0; k < ns; k++) {
            unsigned a = rd16(), v = rd8();
            if (nt < MAX_TOUCH) touch[nt++] = a;
            lx_ram[a] = (lx_u8)v;
        }
        ea = rd8(); ex = rd8(); ey = rd8(); es = rd8(); ep = rd8();
        ecyc = rd32();
        nw = rd16();
        for (k = 0; k < nw; k++) { w_addr[k] = rd16(); w_val[k] = rd8(); if (nt < MAX_TOUCH) touch[nt++] = w_addr[k]; }
        nio = rd16();
        for (k = 0; k < nio; k++) { io_addr[k] = rd16(); io_val[k] = rd8(); }

        if (fn >= lx_test_nfns) { fprintf(stderr, "fn %u inexistente\n", fn); return 2; }

        memset(&cpu, 0, sizeof cpu);
        cpu.a = (lx_u8)ia; cpu.x = (lx_u8)ix; cpu.y = (lx_u8)iy; cpu.s = (lx_u8)is;
        lx_cpu_unpack_p(&cpu, (lx_u8)ip);
        cpu.next_event = 0xFFFFFFFFUL;
        lx_t_io_n = 0;
        lx_t_misroute = 0;

        ret = lx_test_fns[fn](&cpu);

        if (lx_t_misroute) { ok = 0; why = "E/S roteada ao chip errado"; }
        else if (ret != next_pc) { ok = 0; why = "next_pc"; }
        else if (cpu.a != ea || cpu.x != ex || cpu.y != ey || cpu.s != es) { ok = 0; why = "registradores"; }
        else if (lx_cpu_pack_p(&cpu) != ep) { ok = 0; why = "flags(P)"; }
        else if (cpu.cycles != ecyc) { ok = 0; why = "ciclos"; }
        else if (lx_t_io_n != nio || lx_t_io_overflow) { ok = 0; why = "n escritas E/S"; }
        else {
            for (k = 0; k < nio; k++)
                if (lx_t_io_addr[k] != io_addr[k] || lx_t_io_val[k] != io_val[k]) { ok = 0; why = "escrita E/S"; break; }
            for (k = 0; ok && k < nw; k++)
                if (lx_ram[w_addr[k]] != w_val[k]) { ok = 0; why = "escrita RAM"; }
        }

        if (!ok) {
            fails++;
            if (shown++ < 15)
                printf("FALHA vetor %lu fn=%u (%s): in A=%02X X=%02X Y=%02X S=%02X P=%02X | "
                       "esperado A=%02X X=%02X Y=%02X S=%02X P=%02X cyc=%lu | obtido A=%02X X=%02X Y=%02X S=%02X P=%02X cyc=%lu\n",
                       i, fn, why, ia, ix, iy, is, ip, ea, ex, ey, es, ep, (unsigned long)ecyc,
                       cpu.a, cpu.x, cpu.y, cpu.s, lx_cpu_pack_p(&cpu), (unsigned long)cpu.cycles);
        }
        for (k = 0; k < nt; k++) lx_ram[touch[k]] = 0;
        if ((i & 255) == 0) {           /* varredura periódica: escrita fora do esperado */
            unsigned long a;
            for (a = 0; a < LX_RAM_SIZE; a++)
                if (lx_ram[a]) { stray++; if (shown++ < 15) printf("ESCRITA ESTRANHA em $%04lX (vetor %lu)\n", a, i); lx_ram[a] = 0; }
        }
    }
    printf("vetores: %lu  falhas: %lu  escritas estranhas: %lu  funções: %u\n", n, fails, stray, lx_test_nfns);
    return (fails || stray) ? 1 : 0;
}
