---
description: Dispara o subagente certo para um marco do roteiro (ex: /disparar-marco F4)
argument-hint: <F0..F9>
---
Marco pedido: **$ARGUMENTS**.

1. Leia a linha e a seção desse marco em `lynx23do/docs/15-roteiro-estruturado.md`. Se as dependências não estiverem cumpridas, pare e diga quais faltam.
2. Execute o ciclo padrão do roteiro (§2): `/abrir-lote` (backup) → subagente responsável com o **prompt de disparo** do marco (copie-o literalmente e acrescente só o contexto novo) →
   `verificador-independente` → `/fechar-lote`.
3. Marcos que dependem de mim (console, ROM, decisão) terminam com um **pedido explícito** do que preciso fazer, com o resultado esperado.
4. Não paralelize agentes que editem os mesmos arquivos (veja a matriz de paralelismo, §4). Você é o orquestrador: confira por conta própria as contagens que cada agente afirmar.
