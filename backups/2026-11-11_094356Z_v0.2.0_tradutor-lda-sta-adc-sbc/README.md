# Backup 2026-11-11_094356Z — v0.2.0

## Identificação
- **Data/hora:** 2026-11-11 09:43:56 UTC
- **Versão/estágio:** v0.2.0 (tradutor-lda-sta-adc-sbc)
- **Branch / commit de origem:** `ccr-f44b572a-gwjotv` @ `8732897`
- **Conteúdo:** `snapshot/` = cópia integral da árvore de trabalho (exceto `.git/` e `backups/`)

## Resumo do progresso e funcionalidades implementadas até este ponto
v0.2.0 commitada (8732897). Arquitetura aprovada (D1-D9). Tradutor lynx2c para LDA/STA/ADC/SBC (35 opcodes, todos os modos) em blocos retos: optable.json, decoder, IR, vivacidade de flags em bloco reto, emissor C89, CLI. Nucleo de referencia lynxtrace independente. Runtime: lx_mem.c, lx_alu.h, lx_mikey.h. Testes: 29 unitarios + diferencial 557 mil vetores (gcc C89 -O0/-O2), teste de mutacao manual (11 bugs detectados). NAO existe: fluxo de controle, CFG, lx_dispatch/lx_overlay em .c, lynxtrace de perfil.

## Motivo do backup (alterações / próximas tarefas)
Implementar fluxo de controle: BPL BMI BVC BVS BCC BCS BNE BEQ BRA, JMP (abs/(abs)/(abs,X)), JSR, RTS. Adicionar CFG (blocos, lideres), vivacidade de flags entre blocos, emissao multi-bloco com tabela de despacho/overlay, runtime lx_dispatch.c e lx_overlay.c (trampolim lx_run), referencia com PC e programas, teste diferencial de programas com ramificacao, docs/07.

## Regras
Este diretório é **imutável**: não alterar, sobrescrever nem apagar nada aqui dentro.
