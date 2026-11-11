/*
 * lx_alu.h — aritmética decimal (BCD) do 65C02 para ADC/SBC.
 *
 * O caminho BINÁRIO é gerado inline pelo lynx2c (com eliminação de flags mortos).
 * O caminho DECIMAL é raro e fica em lx_alu.c (fora de linha), definindo TODOS os flags.
 *
 * Semântica implementada: descrição de Bruce Clark ("Decimal Mode", 65C02):
 *   ADC: acumulador/carry por 'Seq.1'; V por 'Seq.2' (aritmética com sinal do
 *        nibble alto); N e Z a partir do ACUMULADOR FINAL (diferente do NMOS 6502).
 *   SBC: acumulador por 'Seq.3'; carry e V iguais aos do modo binário; N e Z do
 *        acumulador final.
 * [VERIFY] contra o comportamento do CPU do Lynx (65C02 da WDC/GTE) — entradas BCD
 * VÁLIDAS são verificadas por propriedade (pc-tools/tests/test_reference_core.py);
 * entradas BCD inválidas dependem desta descrição.
 *
 * Nota C89/armcc: usa int com sinal e '&' sobre negativos (complemento de dois,
 * implementação-definida mas universal em gcc/armcc).
 */
#ifndef LX_ALU_H
#define LX_ALU_H

#include "lx_types.h"
#include "lx_cpu_abi.h"

/* Definidos em runtime/src/lx_alu.c (fora de linha). Definem TODOS os flags N Z C V e o acumulador. */
void lx_adc_dec(LxCpu *c, lx_u8 m);
void lx_sbc_dec(LxCpu *c, lx_u8 m);

/* Versões "por valor" para a fase 2 (não obrigam as variáveis locais a ir para a memória). Retornam
 * A | (C << 8) | (V << 9); N e Z são derivados do A final (65C02). */
lx_u32 lx_adc_dec_v(lx_u32 a, lx_u32 c, lx_u32 m);
lx_u32 lx_sbc_dec_v(lx_u32 a, lx_u32 c, lx_u32 m);

#endif /* LX_ALU_H */
