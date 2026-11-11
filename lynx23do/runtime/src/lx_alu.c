/*
 * lx_alu.c — aritmética decimal (BCD) do 65C02 para ADC/SBC. Semântica e fontes: ver lx_alu.h.
 * FORA DE LINHA de propósito: inline, cada ADC/SBC traduzido carregava ~50 instruções ARM a mais
 * (medido com tools/opcode_cost.py). O caminho decimal é raro; a chamada custa pouco.
 */
#include "lynx/lx_alu.h"

static int lx_sx8(int v)           /* byte -> inteiro com sinal */
{
    return (v & 0x80) ? (v - 256) : v;
}

void lx_adc_dec(LxCpu *c, lx_u8 m)
{
    int a = c->a, al, r, sv;

    al = (a & 0x0F) + (m & 0x0F) + c->c;
    if (al >= 0x0A) al = ((al + 0x06) & 0x0F) + 0x10;

    sv = lx_sx8(a & 0xF0) + lx_sx8(m & 0xF0) + al;      /* Seq.2: V */
    c->v = (lx_u8)((sv < -128 || sv > 127) ? 1 : 0);

    r = (a & 0xF0) + (m & 0xF0) + al;                   /* Seq.1 */
    if (r >= 0xA0) r += 0x60;
    c->c = (lx_u8)((r >= 0x100) ? 1 : 0);
    c->a = (lx_u8)(r & 0xFF);
    c->nsrc = c->a;
    c->zsrc = c->a;
}

void lx_sbc_dec(LxCpu *c, lx_u8 m)
{
    int a = c->a, cin = c->c, al, r;
    lx_u32 bin = (lx_u32)c->a + (lx_u32)(m ^ 0xFF) + (lx_u32)cin;   /* resultado binário */

    /* V e C: idênticos ao modo binário */
    c->v = (lx_u8)(((((lx_u32)c->a ^ m) & ((lx_u32)c->a ^ bin)) & 0x80) != 0);
    c->c = (lx_u8)(bin > 0xFF);

    /* Seq.3 (usa o carry de ENTRADA, 'cin', salvo antes de c->c ser sobrescrito) */
    al = (a & 0x0F) - (m & 0x0F) + cin - 1;
    if (al < 0) al = ((al - 0x06) & 0x0F) - 0x10;
    r = (a & 0xF0) - (m & 0xF0) + al;
    if (r < 0) r -= 0x60;
    c->a = (lx_u8)(r & 0xFF);
    c->nsrc = c->a;
    c->zsrc = c->a;
}

