#!/usr/bin/env bash
# check_claude_config.sh — valida a configuração do Claude Code do projeto (.claude/agents, .claude/commands, hook e sugestão de settings).
# Sai com 1 se algo estiver inconsistente. Só Python (stdlib).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
python3 -I - <<'PY'
import json, os, re, sys, glob
ok = True
def bad(msg):
    global ok
    ok = False
    print("ERRO:", msg)

VALID_TOOLS = {"Read", "Grep", "Glob", "Bash", "Edit", "Write", "MultiEdit", "NotebookEdit", "WebFetch", "WebSearch", "Task", "Agent"}
VALID_MODELS = {"sonnet", "opus", "haiku", "inherit"}

def front(path):
    s = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n(.*)", s, re.S)
    if not m:
        bad("%s: sem front matter" % path); return None, ""
    fm = {}
    for ln in m.group(1).splitlines():
        k, _, v = ln.partition(":")
        fm[k.strip()] = v.strip()
    return fm, m.group(2)

agents = sorted(glob.glob(".claude/agents/*.md"))
names = []
for p in agents:
    fm, body = front(p)
    if fm is None: continue
    n = os.path.basename(p)[:-3]
    if fm.get("name") != n: bad("%s: name '%s' difere do arquivo" % (p, fm.get("name")))
    if len(fm.get("description", "")) < 40: bad("%s: description curta demais" % p)
    tools = [t.strip() for t in fm.get("tools", "").split(",") if t.strip()]
    if not tools: bad("%s: sem tools" % p)
    for t in tools:
        if t not in VALID_TOOLS: bad("%s: ferramenta desconhecida %s" % (p, t))
    if fm.get("model") not in VALID_MODELS: bad("%s: model inválido %s" % (p, fm.get("model")))
    if "português" not in body.lower(): bad("%s: prompt não exige português" % p)
    if "backups" in body.lower() and n != "guardiao-processo" and "backup" not in body.lower(): bad("%s: backup" % p)
    if n == "verificador-independente" and any(t in tools for t in ("Edit", "Write", "MultiEdit")): bad("%s: verificador não pode ter ferramentas de escrita" % p)
    if n not in ("guardiao-processo",) and "Write" in tools and n not in ("avaliador-projetos", "arquiteto-multiconsole") and "Edit" not in tools:
        bad("%s: combinação de ferramentas incomum" % p)
    names.append(n)
if len(names) < 9: bad("esperados ≥ 9 subagentes, achei %d" % len(names))
for p in sorted(glob.glob(".claude/commands/*.md")):
    fm, body = front(p)
    if fm is not None and not fm.get("description"): bad("%s: sem description" % p)
    for a in re.findall(r"subagente `([a-z0-9-]+)`", body):
        if a not in names: bad("%s: cita subagente inexistente %s" % (p, a))
# o roteiro cita só agentes que existem; e cada agente aparece no roteiro
road = open("lynx23do/docs/15-roteiro-estruturado.md", encoding="utf-8").read()
for a in set(re.findall(r"subagente `?([a-z]+-[a-z0-9-]+)`?", road)):
    if a not in names: bad("docs/15 cita agente inexistente %s" % a)
for n in names:
    if "`%s`" % n not in road: bad("docs/15 não menciona o agente %s" % n)
try:
    s = json.load(open("scripts/claude-hooks/settings.sugerido.json"))
    cmd = s["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    if "protect_backups.py" not in cmd: bad("settings.sugerido.json não referencia o hook")
    if not os.path.exists("scripts/claude-hooks/protect_backups.py"): bad("hook ausente")
except Exception as e:
    bad("settings.sugerido.json inválido: %s" % e)
if os.path.exists(".claude/settings.json"):
    try: json.load(open(".claude/settings.json"))
    except Exception as e: bad(".claude/settings.json inválido: %s" % e)
print("agentes:", len(names), "| comandos:", len(glob.glob(".claude/commands/*.md")), "|", "OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
PY
python3 scripts/claude-hooks/test_protect_backups.py 2>&1 | tail -1
