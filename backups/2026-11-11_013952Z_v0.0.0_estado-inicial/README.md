# Backup 2026-11-11_013952Z — v0.0.0 (estado inicial, pré-arquitetura)

## Identificação
- **Data/hora:** 2026-11-11 01:39:52 UTC
- **Versão/estágio:** v0.0.0 — estado inicial do repositório, antes de qualquer arquivo do framework Lynx→3DO
- **Branch / commit de origem:** `ccr-f44b572a-gwjotv` @ `2ba59dd`
- **Conteúdo:** `snapshot/` = cópia integral da árvore de trabalho (exceto `.git/` e `backups/`)

## Resumo do progresso até este ponto
- Nenhuma funcionalidade do framework implementada.
- O repositório contém apenas o `README.md` de perfil do GitHub (gerado pelo template do GitHub).

## Motivo do backup (alterações / próximas tarefas)
Início do projeto de conversão Atari Lynx → Panasonic 3DO. Próximas alterações:
1. Criar a estrutura de diretórios (`lynx23do/`: pc-tools, runtime, games, docs, scripts).
2. Escrever a documentação de arquitetura (pipeline AOT, HLE do Suzy, orçamento de memória, riscos).
3. Definir os headers C da camada HLE do Suzy e a ABI entre código gerado e runtime.
4. Criar os scripts de backup/verificação de imutabilidade.

## Regras
Este diretório é **imutável**: não alterar, sobrescrever nem apagar nada aqui dentro.
