# Backup 2026-11-11_161000Z — v0.6.0

## Identificação
- **Data/hora:** 2026-11-11 16:10:00 UTC
- **Versão/estágio:** v0.6.0 (fase2-gerador)
- **Branch / commit de origem:** `ccr-f44b572a-gwjotv` @ `1446c6d`
- **Conteúdo:** `snapshot/` = cópia integral da árvore de trabalho (exceto `.git/`, `backups/` e saídas regeneráveis `build/` e `__pycache__/`)

## Resumo do progresso e funcionalidades implementadas até este ponto
v0.6.0 commitada (1446c6d). Tradutor 178 opcodes, CFG, fase 2 do gerador (rotinas fundidas, registradores locais, limite 32 blocos/rotina, ABI v3), Dormann 6502/65C02 passam nas duas fases, Handy como segunda fonte, ingest/report, expansao ARM 17,9x (7,1 ARM/instr). 114 unitarios, diferencial 895 mil + 10 mil vetores. NAO existe: backend 3DO real (apenas headers e README em runtime/platform/3do), Mikey/Suzy HLE, agendador, Makefile/ISO, nada executado em 3DO ou emulador.

## Motivo do backup (alterações / próximas tarefas)
Backend 3DO real a partir de fontes verificadas do devkit (trapexit/3do-devkit: headers e docs do SDK) e do exemplo funcional XProger/nes-3do (BSD-2): CCB/DrawScreenCels, dois buffers, VBL, pad, CD; Makefile armcc; helper de video/paleta Lynx->3DO testado no host; docs/11 com o que foi verificado e o que depende de autorizacao para executar o armcc.

## Regras
Este diretório é **imutável**: não alterar, sobrescrever nem apagar nada aqui dentro.
