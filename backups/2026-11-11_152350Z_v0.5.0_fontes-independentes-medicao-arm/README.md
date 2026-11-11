# Backup 2026-11-11_152350Z — v0.5.0

## Identificação
- **Data/hora:** 2026-11-11 15:23:50 UTC
- **Versão/estágio:** v0.5.0 (fontes-independentes-medicao-arm)
- **Branch / commit de origem:** `ccr-f44b572a-gwjotv` @ `a355396`
- **Conteúdo:** `snapshot/` = cópia integral da árvore de trabalho (exceto `.git/`, `backups/` e saídas regeneráveis `build/` e `__pycache__/`)

## Resumo do progresso e funcionalidades implementadas até este ponto
v0.5.0 commitada (a355396). 178 opcodes, CFG, flags entre blocos, trampolim lx_run (fase 1: um bloco = uma funcao), SMC de operando imediato, hooks, ABI v2. Dormann 6502 e 65C02 estendida passam. Handy como segunda fonte (opcodes 178/178, ciclos-base 172/178, BCD decimal exaustivo 0 divergencias). Expansao ARM MEDIDA da fase 1: 27x (11,1 ARM/instr), so ~23 KB de 65C02 cabem em 640 KB. ingest (.lnx/BS93) e report.md. 101 unitarios, diferencial 895 mil vetores (blocos) + 10 mil (programas).

## Motivo do backup (alterações / próximas tarefas)
Fase 2 do gerador: roteiros (rotinas) com varios blocos fundidos por goto, registradores A/X/Y/S e flags em variaveis locais, teste de evento so em instrucoes de fluxo e saidas, tabela de despacho com sub-entradas (ABI v3: LxCodeFn recebe 'entry'). Meta: <=10x e <=6 ARM/instr. Rede de seguranca: Dormann + diferencial; oraculo ganha o conceito de 'raizes' (fronteiras de verificacao).

## Regras
Este diretório é **imutável**: não alterar, sobrescrever nem apagar nada aqui dentro.
