---
description: Abre um lote de trabalho: backup obrigatório e confirmação do estado (use antes de qualquer edição)
argument-hint: <versao> <slug> | <marco do roteiro, ex: F4>
---
Abra um lote de trabalho para o marco/tarefa: **$ARGUMENTS**.

1. Delegue ao subagente `guardiao-processo` no **modo ABRIR**: árvore limpa e branch correta, `scripts/make_backup.sh` com resumo FACTUAL do estado atual e a
   lista de tarefas que motivam o backup, e `scripts/check_backups_immutable.sh`.
2. Leia a linha do marco em `lynx23do/docs/15-roteiro-estruturado.md` e repita para mim: objetivo, agente responsável, critérios de aceitação e dependências.
3. Se alguma dependência do marco ainda não está cumprida, **pare e avise** em vez de começar.
4. Mostre o nome do backup criado e o plano em passos curtos; só edite arquivos depois que eu aprovar o plano.
