# CLAUDE.md — lynx23do (porte de Atari Lynx para Panasonic 3DO)

Leia primeiro: `lynx23do/docs/13-handoff-sessao-local.md` (estado, o que falta, o que fazer no PC) e `lynx23do/README.md`.
O projeto está em `lynx23do/`; backups imutáveis em `backups/`; scripts de backup em `scripts/`.

## Regras OBRIGATÓRIAS do usuário (valem para toda sessão)
1. **Backup antes de modificar qualquer arquivo ou estrutura:** `scripts/make_backup.sh <versao> <slug> "<resumo do progresso>" "<motivo / próximas tarefas>"`
   (cópia integral; recusa destino existente). Uma vez por lote de mudanças, ANTES de editar.
2. **Backups são imutáveis:** nunca alterar, sobrescrever ou apagar nada dentro de `backups/`. Conferir com `scripts/check_backups_immutable.sh`.
3. **Cada backup tem `README.md`** com data/hora, versão/estágio, resumo do progresso e lista das alterações/tarefas que o motivaram
   (o script já gera; não editar depois).
4. Idioma: **português** nos docs, commits e respostas ao usuário.

## O que é o projeto
Framework que porta jogos de Atari Lynx para o 3DO (ARM60 @ 12,5 MHz, 2 MB RAM, 1 MB VRAM, Cel Engine): **recompilação estática (AOT)** do
65C02 para **C89** (sem interpretador em tempo de execução) + **HLE** do Suzy (SCB de sprite → Cel → `DrawCels`) e do Mikey.
Estado atual: **v0.8.0**. Tradutor completo e muito testado; backend 3DO escrito e verificado só estaticamente; **nada ainda foi compilado com o
`armcc` nem executado em console/emulador**.

## Comandos (da raiz do repositório)
```bash
export PYTHONPATH=$PWD/lynx23do/pc-tools/lynx2c:$PWD/lynx23do/pc-tools/lynxtrace:$PWD/lynx23do/pc-tools/tests
python3 -m unittest discover -s lynx23do/pc-tools/tests -p 'test_*.py'      # 149 unitários (~4 s)
lynx23do/pc-tools/tests/run_diff.sh                                         # unitários + diferencial: gcc C89 estrito -O0/-O2 (~80 s)
lynx23do/pc-tools/tests/functional/run_dormann.sh                           # suítes de Klaus Dormann (baixa e confere SHA-256; precisa de rede)
lynx23do/scripts/check_headers.sh                                           # headers em C89 estrito (host e config 3DO)
lynx23do/scripts/check_3do_build.sh [DEVKIT=/caminho/3do-devkit]            # estático: ARM big-endian + backend 3DO vs headers reais do SDK
scripts/check_backups_immutable.sh
python3 -m lynx2c --help                                                    # CLI: disasm|cfg|translate|ingest|report|build  (--cpu core|lynx1|lynx2)
```
Requisitos no PC: Python 3.9+ (só biblioteca padrão), gcc (testes diferenciais), clang opcional (`lynx2c report` mede a expansão ARM),
o devkit do 3DO (`armcc`) para o backend real. Windows: use WSL ou Git Bash para os `.sh`.

## Convenções de código
- **C89 estrito** (`-std=c89 -pedantic -Wall -Wextra -Werror`), big-endian-safe (o 3DO é big-endian), sem `malloc` em laço quente, `int` não é 32 bits garantido (usar `lx_u32` etc.).
- Python do lado PC: **somente stdlib** (decisão D1). Tabelas de opcodes são **dados** (`optable.json`, gerado por `tools/gen_optable.py`; não editar à mão).
- **Verificação independente é a regra**: o tradutor é comparado com um oráculo escrito separadamente (`lynxtrace/core65c02.py`, deriva opcodes por regra),
  com Dormann, com Handy/Gearlynx como fontes externas, e com **teste de mutação** (plantar defeito e ver o teste falhar). Todo recurso novo deve
  trazer testes que **comprovadamente falham** quando o código está errado.
- **Não afirmar o que não foi medido.** Separar: verificado / derivado / suposto. Itens `[VERIFY]` ficam marcados até confirmados.
- Sem ROMs, BIOS ou imagens de boot no repositório (`.gitignore`). Nunca commitar jogos.

## Fontes externas (somente leitura; NÃO copiar código GPL)
| Repo | Licença | Uso |
|---|---|---|
| `laoo/Felix` | MIT | precisão por acesso de barramento; HLE da ROM de boot; algoritmo do Suzy |
| `drhelius/Gearlynx` | **GPLv3** | só **fatos de hardware** (tabelas de ciclos etc.), nunca código |
| `libretro/libretro-handy` | zlib-like | referência histórica (cuidado: modelo de ciclos simplificado; trata CB/DB como "dormir") |
| `geo-tp/Cardputer-Game-Station-Emulators` | MIT | estrutura multi-console (`run_<console>`) |
| `trapexit/3do-devkit` | ver repo | headers reais do SDK 3DO, `armcc` |
| `XProger/nes-3do` | BSD-2 | fluxo `armcc→armlink→modbin→3doiso→3DOEncrypt` e CCB |
Resumo e decisões: `lynx23do/docs/12-survey-emuladores-lynx.md`.

## Prioridades (ver docs/13 §5)
0. Se o usuário trouxer os projetos **NES→3DO** e **Master System→3DO** (ele já os tem funcionando no PC): analisar e **reaproveitar** (cadeia de build/ISO,
   backend de vídeo/áudio/entrada, técnicas), registrando o que for aproveitado em `docs/` e `NOTICE`.
1. **Primeiro teste no console (M1)**: `lynx23do/docs/11-plataforma-3do-e-primeiro-teste.md` §6. Aqui o `armcc` do devkit do usuário pode ser executado.
2. **M2**: ticks de 16 MHz, timers do Mikey encadeados + IRQ por nível, agendador por próximo evento, vblank real (docs/12 §3–4).
3. `ingest` de cartucho comercial pelo HLE do boot (docs/12 §6), **M3** (sprites do Suzy, oráculo de sprites), áudio, EEPROM.

## Armadilhas já encontradas (não repetir)
- Teste fraco: stubs de E/S idênticos escondem erro de roteamento → hoje cada chip devolve valores próprios.
- Oráculo que herda a falha do tradutor (líderes de bloco) → `tests/independent.py` calcula líderes por outro algoritmo.
- Handy e Gearlynx **divergem** em pontos de temporização; Felix modela por acesso. Antes de "corrigir", ver docs/12 §1 e §3.
- Jobs longos em segundo plano podem travar: usar `HARNESS_TIMEOUT` e mutação enxuta (`SKIP_UNIT=1 OPTS=-O0`).
