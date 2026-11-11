# Backup 2026-11-11_101919Z — v0.3.0

## Identificação
- **Data/hora:** 2026-11-11 10:19:19 UTC
- **Versão/estágio:** v0.3.0 (fluxo-de-controle)
- **Branch / commit de origem:** `ccr-f44b572a-gwjotv` @ `9697d20`
- **Conteúdo:** `snapshot/` = cópia integral da árvore de trabalho (exceto `.git/` e `backups/`)

## Resumo do progresso e funcionalidades implementadas até este ponto
v0.3.0 commitada (9697d20). 49 opcodes: LDA STA ADC SBC, Bcc/BRA, JMP (abs/(abs)/(abs,X)), JSR, RTS. CFG por descida recursiva, liveness de flags entre blocos (ponto fixo, opcao precise_exits), emissao multi-bloco com tabela de despacho/overlay, runtime lx_dispatch.c/lx_overlay.c/lx_mem.c (trampolim lx_run). Referencia independente lynxtrace. 55 unitarios, diferencial de blocos (557 mil vetores) e de programas (9,7 mil, trampolim real), teste de mutacao (18 mutantes). NAO existem: CMP/AND/ORA/EOR, INC/DEC, registradores X/Y, transferencias, pilha (PHA/PLA/PHP/PLP), flags (CLC/SEC/CLD/SED), shifts, RTI/BRK, NOP.

## Motivo do backup (alterações / próximas tarefas)
Completar o conjunto de uso comum do 65C02 (129 opcodes novos, total 178): ORA AND EOR CMP BIT, LDX LDY STX STY STZ, CPX CPY, INC DEC ASL LSR ROL ROR (acc e memoria), TSB TRB, INX INY DEX DEY, Txx, CLC SEC CLI SEI CLV CLD SED, NOP, PHA PLA PHX PLX PHY PLY PHP PLP, BRK RTI. Modos novos zpy/acc/brk; RMW; atualizar optable, decoder, CFG (BRK), liveness (PHP usa NZCV), emissor, referencia, geradores de vetores/programas e docs.

## Regras
Este diretório é **imutável**: não alterar, sobrescrever nem apagar nada aqui dentro.
