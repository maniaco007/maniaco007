#!/usr/bin/env bash
# export_standalone.sh — cria um repositório git NOVO e independente só com o projeto lynx23do.
#
# Copia (respeitando .gitignore; sem histórico, sem build/): lynx23do/, backups/, scripts/, CLAUDE.md, README.md de projeto e .gitignore.
# A estrutura de pastas é mantida (os scripts e o CLAUDE.md dependem de lynx23do/, backups/ e scripts/ na raiz).
# Nunca altera o repositório de origem nem backups/ de origem.
#
# Uso:   scripts/export_standalone.sh <diretorio-destino>        (não pode existir, ou deve estar vazio)
# Depois (no destino):
#   git remote add origin https://github.com/<dono>/<novo-repo>.git && git push -u origin main
set -euo pipefail
if [ "$#" -ne 1 ]; then sed -n '2,12p' "$0"; exit 2; fi
DEST="$1"
SRC="$(git rev-parse --show-toplevel)"
cd "$SRC"
if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
  echo "ERRO: $DEST já existe e não está vazio." >&2; exit 1
fi
mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"
case "$DEST/" in "$SRC"/*) echo "ERRO: o destino não pode ficar dentro do repositório de origem." >&2; exit 1;; esac

# arquivos versionados + novos não ignorados, só das pastas do projeto
git ls-files --cached --others --exclude-standard -z -- lynx23do backups scripts CLAUDE.md \
  | tar --null -T - -cf - | tar -xf - -C "$DEST"

cp lynx23do/.gitignore "$DEST/.gitignore"
cat > "$DEST/README.md" <<'MD'
# lynx23do — Atari Lynx → Panasonic 3DO

Framework de **recompilação estática (65C02 → C89)** + **HLE do Suzy (Cel Engine)** para portar jogos de Atari Lynx para o 3DO.

- **Comece por:** [`CLAUDE.md`](CLAUDE.md) (regras e comandos), [`lynx23do/docs/13-handoff-sessao-local.md`](lynx23do/docs/13-handoff-sessao-local.md) (estado e próximos passos) e [`lynx23do/README.md`](lynx23do/README.md).
- Estado: v0.8.0 — tradutor verificado; backend 3DO escrito mas **ainda não compilado com `armcc` nem executado em console**.
- `backups/` contém backups **imutáveis** com README próprio (regra do projeto); `scripts/make_backup.sh` cria novos.
- Sem ROMs/BIOS no repositório.
MD

cd "$DEST"
git init -q -b main
git add -A
git -c user.name="${GIT_AUTHOR_NAME:-lynx23do}" -c user.email="${GIT_AUTHOR_EMAIL:-lynx23do@users.noreply.github.com}" \
    commit -q -m "lynx23do: importacao inicial (exportado do repositorio de origem em $(date -u +%Y-%m-%d))"
echo "OK: repositório criado em $DEST ($(git ls-files | wc -l) arquivos)."
echo "Próximo passo: git remote add origin https://github.com/<dono>/<novo-repo>.git && git push -u origin main"
