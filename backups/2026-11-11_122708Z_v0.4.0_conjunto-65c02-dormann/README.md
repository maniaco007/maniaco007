# Backup 2026-11-11_122708Z — v0.4.0

## Identificação
- **Data/hora:** 2026-11-11 12:27:08 UTC
- **Versão/estágio:** v0.4.0 (conjunto-65c02-dormann)
- **Branch / commit de origem:** `ccr-f44b572a-gwjotv` @ `75da6cb`
- **Conteúdo:** `snapshot/` = cópia integral da árvore de trabalho (exceto `.git/`, `backups/` e saídas regeneráveis `build/` e `__pycache__/`)

## Resumo do progresso e funcionalidades implementadas até este ponto
v0.4.0 commitada (75da6cb). 178 opcodes (NMOS documentados + 65C02 de uso comum), CFG, liveness entre blocos, trampolim lx_run, SMC de operando imediato (--smc-operand), hooks (--hook). Suites funcionais de Klaus Dormann (6502: 96,7 M ciclos; 65C02 estendida: 67,1 M) PASSAM pelo pipeline completo com 5 trechos dispensados por hook. 76 unitarios, diferencial 895 mil vetores (blocos) + 10 mil (programas), ~45 mutantes. NAO existem: perfil dinamico (lynxtrace), estagios A-C (ingest/discover/report), WAI/STP, ciclos verificados por fonte independente, medicao de expansao de codigo ARM, fase 2 do gerador.

## Motivo do backup (alterações / próximas tarefas)
Fontes independentes e medicao: (1) comparar opcodes e ciclos base com o emulador Handy (dado de referencia, sem copiar codigo) e fixar o resultado em teste; (2) medir a expansao REAL de codigo ARM big-endian (clang) do codigo traduzido, substituindo a hipotese do docs/04; (3) estagio A (ingest .lnx/BS93), relatorio de elegibilidade (report) e docs.

## Regras
Este diretório é **imutável**: não alterar, sobrescrever nem apagar nada aqui dentro.
