/*
 * lx_test_stubs.c — E/S falsa e agendador nulo para o teste diferencial.
 * Regras IGUAIS às do núcleo de referência (core65c02.py: io_value / io_writes).
 *
 * Cada chip devolve um valor DIFERENTE e conta 'misroute' se receber endereço
 * fora da sua faixa: assim classificação de região errada (Suzy x Mikey x RAM)
 * é detectada pelo harness (ver teste de mutação em docs/06).
 */
#include "lynx/lx_cpu_abi.h"
#include "lynx/lx_mem.h"
#include "lynx/lx_suzy.h"
#include "lynx/lx_mikey.h"

#define LX_T_IO_MAX 64
unsigned lx_t_io_n;
lx_u32   lx_t_io_addr[LX_T_IO_MAX];
lx_u8    lx_t_io_val[LX_T_IO_MAX];
unsigned lx_t_io_overflow;
unsigned lx_t_misroute;

static void io_log(lx_u32 addr, lx_u8 val)
{
    if (lx_t_io_n < LX_T_IO_MAX) {
        lx_t_io_addr[lx_t_io_n] = addr;
        lx_t_io_val[lx_t_io_n] = val;
        lx_t_io_n++;
    } else {
        lx_t_io_overflow++;
    }
}

static int in_suzy(lx_u32 a)  { return a >= LX_SUZY_BASE  && a <= LX_SUZY_END; }
static int in_mikey(lx_u32 a) { return a >= LX_MIKEY_BASE && a <= LX_MIKEY_END; }

lx_u8 lx_suzy_read(lx_u32 addr)
{
    if (!in_suzy(addr)) lx_t_misroute++;
    return (lx_u8)((addr * 7 + 13) & 0xFF);
}
void lx_suzy_write(lx_u32 addr, lx_u8 val)
{
    if (!in_suzy(addr)) lx_t_misroute++;
    io_log(addr, val);
}
lx_u8 lx_mikey_read(lx_u32 addr)
{
    if (!in_mikey(addr)) lx_t_misroute++;
    return (lx_u8)((addr * 11 + 5) & 0xFF);
}
void lx_mikey_write(lx_u32 addr, lx_u8 val)
{
    if (!in_mikey(addr)) lx_t_misroute++;
    io_log(addr, val);
}

/* nunca deve ser chamado: o harness fixa next_event = 0xFFFFFFFF */
lx_u32 lx_sched_service(LxCpu *cpu, lx_u32 next_pc)
{
    (void)cpu;
    return next_pc;
}
