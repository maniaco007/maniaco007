# Trava técnica da regra "backups são imutáveis" (opcional, mas recomendada)

`protect_backups.py` é um *hook* do Claude Code que **bloqueia** qualquer edição/remoção/movimentação dentro de `backups/` feita pelo
agente principal **ou por qualquer subagente**, e deixa passar leituras e a criação de backup novo (`scripts/make_backup.sh`).
É proteção contra erro; a conferência definitiva continua sendo `scripts/check_backups_immutable.sh`.

## Ativar (decisão sua — a sessão de nuvem não pôde gravar a configuração do próprio agente)
```bash
mkdir -p .claude
cp scripts/claude-hooks/settings.sugerido.json .claude/settings.json      # se já existir um settings.json, mescle as chaves "hooks" e "permissions"
python3 scripts/claude-hooks/test_protect_backups.py                      # deve imprimir OK
```
- No Windows (sem WSL) troque `python3` por `python` no comando do hook.
- `settings.sugerido.json` também libera, sem pedir confirmação, só comandos de **verificação** e o `make_backup.sh`, e proíbe `git push --force` e
  `git reset --hard`. **Não** libera o `armcc`/`make` do devkit, nem `git push`, nem `git commit`: esses continuam pedindo confirmação.
- Para desativar: apague `.claude/settings.json` (ou a chave `hooks`).
