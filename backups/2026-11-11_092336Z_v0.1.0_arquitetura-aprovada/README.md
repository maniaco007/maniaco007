# Backup 2026-11-11_092336Z — v0.1.0

## Identificação
- **Data/hora:** 2026-11-11 09:23:36 UTC
- **Versão/estágio:** v0.1.0 (arquitetura-aprovada)
- **Branch / commit de origem:** `ccr-f44b572a-gwjotv` @ `1776005`
- **Conteúdo:** `snapshot/` = cópia integral da árvore de trabalho (exceto `.git/` e `backups/`)

## Resumo do progresso e funcionalidades implementadas até este ponto
Arquitetura aprovada pelo usuário. Entregue: docs 01-05 (fluxo ROM->iso, pipeline AOT, HLE Suzy->Cel, orçamento 2 MB, riscos D1-D9); headers C89 do runtime (ABI, overlays, Suzy, Cel, plataforma) compilando em C89 estrito; scripts de backup/imutabilidade; manifest template. Ainda NÃO existe: decoder/tradutor de opcodes, lynxtrace, runtime .c.

## Motivo do backup (alterações / próximas tarefas)
Implementar o primeiro tradutor de opcodes (LDA, STA, ADC, SBC, todos os modos 65C02): optable.json, decoder, IR, vivacidade de flags, emissor C89, núcleo de referência, runtime/src/lx_mem.c, lx_alu.h, lx_mikey.h e bateria de teste diferencial; atualizar READMEs/docs.

## Regras
Este diretório é **imutável**: não alterar, sobrescrever nem apagar nada aqui dentro.
