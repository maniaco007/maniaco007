#!/usr/bin/env python3
"""Hook PreToolUse do Claude Code: faz cumprir a regra "backups são imutáveis" (CLAUDE.md, regra 2).

Lê o JSON do evento na entrada padrão. Sai com código 2 (bloqueia a ferramenta e mostra a mensagem ao Claude) quando:
  - Edit/Write/MultiEdit/NotebookEdit tem como alvo um caminho dentro de backups/;
  - um comando Bash tenta ESCREVER/APAGAR/MOVER algo dentro de backups/ (rm, mv, cp para dentro, sed -i, tee, redirecionamento,
    truncate, chmod, git clean/checkout/restore/rm...), exceto a criação de backup NOVO por scripts/make_backup.sh.
Leituras (cat, ls, diff, grep...) passam. É uma trava contra ERRO (do agente ou de um subagente), não contra um adversário
determinado: a conferência definitiva é scripts/check_backups_immutable.sh. Só biblioteca padrão; Linux/macOS/WSL/Windows.

Ativação: ver scripts/claude-hooks/README.md (copiar settings.sugerido.json para .claude/settings.json — decisão do usuário).
Teste: python3 scripts/claude-hooks/test_protect_backups.py
"""
import json
import re
import sys

WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
BACKUPS = re.compile(r"(^|[\\/\s'\"=])backups([\\/]|$)")
MUTATORS = re.compile(
    r"(^|[\s;&|(])(rm|rmdir|mv|truncate|chmod|chown|shred|unlink|ln|install|dd|rsync|"
    r"git\s+(rm|clean|checkout|restore|reset|stash|mv|apply)|sed\s+(-[a-zA-Z]*i)|perl\s+-[a-zA-Z]*i|tee|touch)\b")
REDIRECT_INTO_BACKUPS = re.compile(r">>?\s*['\"]?[^\s;&|]*backups[\\/]")
CP_INTO_BACKUPS = re.compile(r"\b(cp|rsync|tar\s+[^|;&]*-x[^|;&]*-C|unzip[^|;&]*-d|mkdir)\b[^|;&]*\bbackups[\\/]")


def decide(ev):
    """Retorna None (permitir) ou a mensagem de bloqueio."""
    tool, inp = ev.get("tool_name", ""), ev.get("tool_input", {}) or {}
    if tool in WRITE_TOOLS:
        path = (inp.get("file_path") or inp.get("notebook_path") or "").replace("\\", "/")
        if BACKUPS.search(path) or "/backups/" in path:
            return "%s em %s" % (tool, path)
    elif tool == "Bash":
        cmd = inp.get("command", "")
        if "make_backup.sh" in cmd and not MUTATORS.search(cmd.replace("make_backup.sh", "")):
            return None                   # criar backup NOVO é o caminho permitido
        if BACKUPS.search(cmd) and (MUTATORS.search(cmd) or REDIRECT_INTO_BACKUPS.search(cmd) or CP_INTO_BACKUPS.search(cmd)):
            return "comando que modifica backups/: %s" % cmd[:160]
    return None


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        sys.exit(0)                       # evento ilegível: não bloquear por engano
    why = decide(ev)
    if why:
        sys.stderr.write("BLOQUEADO (regra do projeto: backups são imutáveis): %s\n"
                         "Para registrar um estado novo use scripts/make_backup.sh <versao> <slug> \"<resumo>\" \"<motivo>\".\n" % why)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
