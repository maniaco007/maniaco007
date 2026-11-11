#!/usr/bin/env bash
# make_backup.sh — cria um backup IMUTÁVEL e documentado do projeto.
#
# Regras (preferências obrigatórias do projeto):
#   1. Rodar ANTES de qualquer modificação de arquivo/estrutura.
#   2. Nunca altera/sobrescreve/apaga backups existentes (recusa se o destino existir).
#   3. Cada backup contém um README.md com: data/hora, versão/estágio,
#      resumo do progresso e lista de alterações/tarefas que motivaram o backup.
#
# Uso:
#   scripts/make_backup.sh <versao> <slug> "<resumo do progresso>" "<motivo / próximas tarefas>"
# Exemplo:
#   scripts/make_backup.sh v0.2.0 antes-do-tradutor-adc-sbc \
#       "Arquitetura aprovada; headers HLE prontos." \
#       "Implementar ADC/SBC/LDA/STA no lynx2c."
set -euo pipefail

if [ "$#" -ne 4 ]; then
  sed -n '2,16p' "$0"; exit 2
fi
VERSAO="$1"; SLUG="$2"; RESUMO="$3"; MOTIVO="$4"

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

TS="$(date -u +%Y-%m-%d_%H%M%SZ)"
HUMAN="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"
COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'sem-commit')"
BRANCH="$(git branch --show-current 2>/dev/null || echo '?')"
DEST="backups/${TS}_${VERSAO}_${SLUG}"

if [ -e "$DEST" ]; then
  echo "ERRO: $DEST já existe — backups são imutáveis." >&2; exit 1
fi

mkdir -p "$DEST/snapshot"
# Cópia integral da árvore de trabalho (inclui arquivos não versionados),
# exceto .git (histórico já preservado pelo git) e backups (evita recursão).
tar --exclude=./.git --exclude=./backups -cf - . | tar -xf - -C "$DEST/snapshot"

cat > "$DEST/README.md" <<EOF
# Backup ${TS} — ${VERSAO}

## Identificação
- **Data/hora:** ${HUMAN}
- **Versão/estágio:** ${VERSAO} (${SLUG})
- **Branch / commit de origem:** \`${BRANCH}\` @ \`${COMMIT}\`
- **Conteúdo:** \`snapshot/\` = cópia integral da árvore de trabalho (exceto \`.git/\` e \`backups/\`)

## Resumo do progresso e funcionalidades implementadas até este ponto
${RESUMO}

## Motivo do backup (alterações / próximas tarefas)
${MOTIVO}

## Regras
Este diretório é **imutável**: não alterar, sobrescrever nem apagar nada aqui dentro.
EOF

chmod -R a-w "$DEST"
echo "Backup criado: $DEST"
