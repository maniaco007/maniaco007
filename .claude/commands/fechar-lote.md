---
description: Fecha um lote: verificação independente, checklist do guardião, documentação e commit
argument-hint: <resumo curto do lote>
---
Feche o lote: **$ARGUMENTS**.

1. Delegue ao subagente `verificador-independente` a revisão da mudança (`git diff`/`git status`) com o protocolo dele. **Não** repasse o relatório do implementador como se fosse verdade: ele deve reexecutar tudo.
2. Se o veredito for REPROVADO, ou APROVADO COM RESSALVAS com achado de severidade alta, **pare** e liste os achados para eu decidir; não faça commit.
3. Se APROVADO: delegue ao `guardiao-processo` no **modo FECHAR** (backups íntegros, testes, documentação com números reais, licenças, higiene do commit).
4. Mostre o checklist completo e a mensagem de commit proposta (português; cita o backup prévio). **Só faça `git commit` depois da minha confirmação.** Não faça `git push`.
