/*
 * lx_cpu_abi.h — ABI (contrato) entre o código C GERADO pelo lynx2c e o runtime.
 *
 * Este header descreve só o CONTRATO; o gerador de opcodes ainda não existe.
 * Qualquer mudança aqui exige regenerar todo o código traduzido (ver
 * LX_ABI_VERSION, conferido pelo código gerado em tempo de compilação).
 *
 * Modelo de execução (docs/02-pipeline-aot-pc.md §7):
 *   - Cada unidade traduzida é uma função LxCodeFn(LxCpu*) que executa UM
 *     bloco básico (fase 1) ou uma rotina com entradas (fase 2).
 *   - O valor de retorno diz o que fazer a seguir (próximo PC do Lynx ou um
 *     código especial). Um trampolim (lx_run) despacha — sem recursão
 *     ilimitada no stack do ARM (armcc não garante tail calls).
 *   - JSR/RTS usam a pilha EMULADA em $0100-$01FF (os jogos mexem nela:
 *     PHA/PLA de endereços, "RTS trick", troca de tarefas). RTS verifica o
 *     endereço desempilhado; se bater com o chamador C, retorna nativamente.
 *   - NÃO existe interpretador de 65C02 em tempo de execução. PC sem código
 *     traduzido => lx_unresolved(pc) (aborta com relatório; ver
 *     docs/05-riscos-e-decisoes-abertas.md, D2).
 */
#ifndef LX_CPU_ABI_H
#define LX_CPU_ABI_H

#include "lx_types.h"
#include "lx_config.h"

#define LX_ABI_VERSION 3   /* v3: LxCodeFn(cpu, entry) com sub-entradas; macros LX_PUSH8/PULL8/PACK_P/UNPACK_P p/ fase 2;
                              * v2: LX_SCHED_CHECK com chamada final; lx_adc_dec/lx_sbc_dec fora de linha */

/* Contexto da CPU. Flags N/Z são PREGUIÇOSOS: guardam o valor que os
 * originou; o lynx2c só materializa N/Z quando a análise de vivacidade de
 * flags prova que alguém os lê (a maioria dos flags é morta).
 *   N = (nsrc & 0x80) != 0      Z = (zsrc == 0)
 * N e Z são campos separados porque BIT os desacopla (N = M7, Z = (A&M)==0). */
typedef struct LxCpu {
    lx_u8  a, x, y, s;
    lx_u8  c, v, d, i;          /* flags explícitos, 0 ou 1 */
    lx_u8  nsrc, zsrc;          /* fontes preguiçosas de N e Z */
    lx_u8  b;                   /* flag B (só relevante em PHP/BRK) */
    lx_u8  _pad;
    lx_u32 cycles;              /* ciclos Lynx desde o último lx_sched_service() */
    lx_u32 next_event;          /* limiar: quando cycles >= next_event, serviço */
    lx_u32 irq_pending;         /* máscara de IRQs levantados pelo agendador */
} LxCpu;

/* P empacotado (PHP, interrupções) <-> campos */
LX_INLINE lx_u8 lx_cpu_pack_p(const LxCpu *c)
{
    return (lx_u8)( ((c->nsrc & 0x80) ? 0x80 : 0) | (c->v ? 0x40 : 0) | 0x20 |
                    (c->b ? 0x10 : 0) | (c->d ? 0x08 : 0) | (c->i ? 0x04 : 0) |
                    (c->zsrc == 0 ? 0x02 : 0) | (c->c ? 0x01 : 0) );
}
LX_INLINE void lx_cpu_unpack_p(LxCpu *c, lx_u8 p)
{
    c->nsrc = (lx_u8)(p & 0x80);
    c->zsrc = (lx_u8)((p & 0x02) ? 0 : 1);
    c->v = (lx_u8)((p >> 6) & 1);  c->b = (lx_u8)((p >> 4) & 1);
    c->d = (lx_u8)((p >> 3) & 1);  c->i = (lx_u8)((p >> 2) & 1);
    c->c = (lx_u8)(p & 1);
}

/* ---- Valores de retorno de LxCodeFn --------------------------------------- */
/* 0x0000..0xFFFF : continuar a execução neste PC do Lynx (via lx_dispatch)    */
#define LX_PC_RETURN   0x10000UL  /* RTS/RTI "limpo": voltar ao chamador C        */
#define LX_PC_YIELD    0x10001UL  /* ponto de sincronismo: frame pronto p/ apresentar */
#define LX_PC_HALT     0x10002UL  /* parada (STP/erro fatal controlado)           */

/* 'entry' escolhe o líder (sub-entrada) onde a rotina começa: 0 = raiz. Funções de bloco único (fase 1) o ignoram. */
typedef lx_u32 (*LxCodeFn)(LxCpu *cpu, lx_u32 entry);

/* ---- Fase 2: registradores e flags em VARIÁVEIS LOCAIS da rotina (o código gerado usa estas macros; exigem lx_mem.h) ----
 * Pilha do 65C02 em $0100-$01FF sobre a variável local 's'. P empacotado a partir das variáveis locais de flag
 * (B só existe no P EMPILHADO: quem empilha faz '| 0x10'; PLP/RTI o ignoram). */
#define LX_PUSH8(sv, val)  do { lx_ram[0x100 | (sv)] = (lx_u8)(val); (sv) = ((sv) - 1) & 0xFF; } while (0)
#define LX_PULL8(sv)       (lx_ram[0x100 | ((sv) = ((sv) + 1) & 0xFF)])
#define LX_PACK_P(nsrc, v, d, i, zsrc, c) \
    ((lx_u32)(0x20 | ((nsrc) & 0x80) | ((v) ? 0x40 : 0) | ((d) ? 0x08 : 0) | ((i) ? 0x04 : 0) | \
              (((zsrc) == 0) ? 0x02 : 0) | ((c) ? 0x01 : 0)))
#define LX_UNPACK_P(p, nsrc, zsrc, v, d, i, c)                                        \
    do { lx_u32 lx_p_ = (p); (nsrc) = lx_p_ & 0x80; (zsrc) = (lx_p_ & 0x02) ? 0 : 1;   \
         (v) = (lx_p_ >> 6) & 1; (d) = (lx_p_ >> 3) & 1; (i) = (lx_p_ >> 2) & 1; (c) = lx_p_ & 1; } while (0)

/* ---- Trampolim e despacho --------------------------------------------------- */
/* Executa a partir de 'pc' até LX_PC_YIELD/LX_PC_HALT. Chamado pelo laço
 * principal do 3DO uma vez por frame (ver runtime/platform). */
lx_u32 lx_run(LxCpu *cpu, lx_u32 pc);

/* Executa o bloco traduzido que começa em 'pc' e devolve o resultado dele
 * (próximo PC ou LX_PC_*). Ordem de busca: hook HLE (lx_hook_find) -> tabela
 * do overlay ativo em 'pc' (busca binária). Se não houver nenhum, chama
 * lx_unresolved(pc) e devolve LX_PC_HALT. */
lx_u32 lx_dispatch(LxCpu *cpu, lx_u32 pc);

/* PC sem código traduzido: erro fatal CONTROLADO. Registra o PC em
 * lx_unresolved_pc (e incrementa lx_unresolved_count); a camada de plataforma
 * escreve "unresolved.log" (host) / console de debug (3DO). O log alimenta o
 * próximo ciclo do lynx2c como novo seed (docs/02 §3, estágio B). Não aborta o
 * processo: lx_dispatch devolve LX_PC_HALT e lx_run encerra. */
void lx_unresolved(lx_u32 pc);
extern lx_u32 lx_unresolved_pc;
extern lx_u32 lx_unresolved_count;

/* ---- Contabilidade de ciclos / eventos ---------------------------------------
 * O código gerado soma, ao FIM de cada bloco, o custo em ciclos 65C02 do bloco
 * (constante em tempo de tradução) e testa o limiar. Em arestas de retorno
 * (branch para trás) a verificação é obrigatória: loops de espera por vblank/IRQ
 * dependem de o tempo avançar.
 * lx_sched_service() avança timers do Mikey (hblank/vblank/áudio), atualiza
 * SPRSYS/busy do Suzy e pode DESVIAR para o vetor de IRQ (empilha PC e P). */
lx_u32 lx_sched_service(LxCpu *cpu, lx_u32 next_pc);

/* Quando o agendador devolve LX_PC_YIELD, o PC onde retomar fica aqui (lx_machine.c; nos testes, em lx_t_yield_pc). */
extern lx_u32 lx_resume_pc;

/* lx_sched_service() devolve 'next_pc' quando nada aconteceu (ou o PC do vetor de IRQ / LX_PC_YIELD): por isso o
 * retorno dela É o retorno do bloco. Com CHAMADA FINAL o compilador não precisa de quadro de pilha no caminho
 * comum (medido: o custo fixo por bloco caiu de 18 para poucas instruções ARM; ver docs/04 §3). */
#define LX_SCHED_CHECK(cpu, ncycles, next_pc)                              \
    do {                                                                    \
        (cpu)->cycles += (ncycles);                                         \
        if ((cpu)->cycles >= (cpu)->next_event)                             \
            return lx_sched_service((cpu), (next_pc));                      \
    } while (0)

#endif /* LX_CPU_ABI_H */
