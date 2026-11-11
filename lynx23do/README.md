# lynx23do — Atari Lynx → Panasonic 3DO (recompilação estática + HLE)

Framework para portar jogos selecionados de Atari Lynx para rodar **nativamente** no 3DO
(ARM60 @ 12,5 MHz, 2 MB DRAM, 1 MB VRAM, Cel Engine), combinando:

- **Recompilação estática (AOT)** do 65C02 → C89 (sem interpretador em tempo de execução);
- **HLE do Suzy**: SCBs de sprite viram Cels e são desenhados por `DrawCels()`.

**v0.8.0 (tradutor):** modelos de CPU `--cpu core|lynx1|lynx2` — NOPs indocumentados (`CB`/`DB` incluídos), Rockwell `RMB/SMB/BBR/BBS` no Lynx II, cabeçalho `LNX2` (docs/12 §2.1).

**v0.7.1 (documentação):** survey de 4 emuladores de Lynx em `docs/12` (tabela de ciclos dos 178 opcodes confere 100 % com o Gearlynx; correções de R11; plano M2/M3).

**Estágio atual: v0.7.0 — tradutor de 178 opcodes com fase 2 (17,9×, 7,1 ARM/instr), validado por Dormann; **backend 3DO escrito e
verificado estaticamente** contra os headers reais do SDK (devkit do trapexit) e o fluxo do nes-3do; demo 65C02 rodando de ponta a
ponta no PC. **Falta o primeiro teste no console:** compilar com o `armcc` do SEU devkit e rodar no ODE — passo a passo em
`docs/11` §6.** Ainda sem timers/IRQ do Mikey, sem Suzy (sprites) e sem áudio: só homebrew que desenha por CPU roda.

## Leia nesta ordem
1. [`docs/01-visao-geral-e-fluxo-de-dados.md`](docs/01-visao-geral-e-fluxo-de-dados.md) — modelo mental ROM → `.iso`
2. [`docs/02-pipeline-aot-pc.md`](docs/02-pipeline-aot-pc.md) — como achar código, separar dados, gerar o `.c`
3. [`docs/03-hle-suzy.md`](docs/03-hle-suzy.md) — Suzy → Cel Engine
4. [`docs/04-orcamento-memoria-2mb.md`](docs/04-orcamento-memoria-2mb.md) — cabe em 2 MB?
5. [`docs/05-riscos-e-decisoes-abertas.md`](docs/05-riscos-e-decisoes-abertas.md) — decisões D1–D9 (aprovadas) e riscos
6. [`docs/06-traducao-lda-sta-adc-sbc.md`](docs/06-traducao-lda-sta-adc-sbc.md) — primeiro tradutor e o que os testes provam
7. [`docs/07-fluxo-de-controle.md`](docs/07-fluxo-de-controle.md) — CFG, JSR/RTS, flags entre blocos, mutação
8. [`docs/08-conjunto-65c02-e-validacao-independente.md`](docs/08-conjunto-65c02-e-validacao-independente.md) — 178 opcodes, Dormann, limites
9. [`docs/09-fontes-independentes-medicao-arm-e-ingest.md`](docs/09-fontes-independentes-medicao-arm-e-ingest.md) — Handy, expansão ARM medida, ingest/report
10. [`docs/10-fase2-gerador.md`](docs/10-fase2-gerador.md) — rotinas fundidas, 17,9×, o limite de blocos, bugs achados
11. [`docs/11-plataforma-3do-e-primeiro-teste.md`](docs/11-plataforma-3do-e-primeiro-teste.md) — **o que reaproveitei do GitHub, o que foi verificado, como fazer o 1º teste no ODE**
12. [`docs/12-survey-emuladores-lynx.md`](docs/12-survey-emuladores-lynx.md) — **survey de Felix, Gearlynx, libretro-handy e Cardputer: modelo de ticks, timers do Mikey, especificação do Suzy, boot HLE, padrões para outros consoles**
13. [`docs/13-handoff-sessao-local.md`](docs/13-handoff-sessao-local.md) — **handoff para a sessão local (PC): estado, o que falta**
15. [`docs/15-roteiro-estruturado.md`](docs/15-roteiro-estruturado.md) — **roteiro: marcos F0–F10, subagentes (`.claude/agents/`), critérios de aceitação** (o `docs/14` será gerado pelo marco F1)

## Estrutura
```
lynx23do/
├── docs/                    arquitetura (acima)
├── pc-tools/                roda NO PC (Python 3, só stdlib — decisão D1)
│   ├── lynx2c/              tradutor AOT: decode → CFG → lift → liveness → emit  (ingest/discover: a fazer)
│   ├── lynxtrace/           núcleo 65C02 de referência (oráculo; subconjunto atual) + perfil dinâmico (a fazer)
│   ├── spritecook/          sprites Suzy → dados de Cel (formato "packed" do 3DO) + PLUT
│   ├── pack3do/             Makefile do SDK, árvore do disco, ISO
│   └── tests/               testes diferenciais e de determinismo
├── runtime/                 código NATIVO (C89): 3DO e host
│   ├── include/lynx/        headers públicos (API do HLE, ABI do código gerado)
│   ├── src/                 núcleo portável: lx_mem, lx_dispatch, lx_overlay prontos; sched/Suzy/Mikey a implementar
│   ├── platform/3do/        backend 3DO (DrawCels, VRAM, pad, CD) — a implementar
│   ├── platform/host/       backend PC (rasterizador de software) — a implementar
│   └── tests/               header_check.c (C89 estrito)
├── games/                   perfis por jogo (manifest.toml). SEM ROMs.
│   └── _template/
└── scripts/                 check_headers.sh
```
Fora deste diretório (raiz do repositório):
- `backups/` — backups **imutáveis**, cada um com `README.md`;
- `scripts/make_backup.sh`, `scripts/check_backups_immutable.sh`.

## Verificação disponível hoje
```
lynx23do/scripts/check_headers.sh          # headers em C89 estrito (gcc), configs host e 3DO
scripts/check_backups_immutable.sh         # backups/ só recebe adições
scripts/check_3do_build.sh  [DEVKIT=...]   # estático: ARM big-endian C89 + backend 3DO vs headers reais do SDK
lynx23do/pc-tools/tests/run_diff.sh        # 149 unitários + diferencial (910 mil vetores de blocos + 13,9 mil de programas, -O0/-O2)
lynx23do/pc-tools/tests/functional/run_dormann.sh   # suítes de Klaus Dormann (baixa e confere SHA-256; precisa de rede)
```
O armcc/SDK 3DO **não** está disponível neste ambiente; a compatibilidade com o SDK
(assinaturas e formatos do CCB) está marcada `[VERIFY]` nos headers.

## Regras de trabalho
- **Backup antes de modificar** (`scripts/make_backup.sh`); backups nunca são alterados.
- Sem ROMs/BIOS no repositório (`.gitignore`).
- C89, big-endian-safe, sem interpretador em T3 (ver invariantes em `docs/01` §7).
