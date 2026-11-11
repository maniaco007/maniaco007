# lynx23do — Atari Lynx → Panasonic 3DO (recompilação estática + HLE)

Framework para portar jogos selecionados de Atari Lynx para rodar **nativamente** no 3DO
(ARM60 @ 12,5 MHz, 2 MB DRAM, 1 MB VRAM, Cel Engine), combinando:

- **Recompilação estática (AOT)** do 65C02 → C89 (sem interpretador em tempo de execução);
- **HLE do Suzy**: SCBs de sprite viram Cels e são desenhados por `DrawCels()`.

**Estágio atual: v0.1.0 — arquitetura, aguardando aprovação.** Não há tradutor de opcodes
nem inicialização do Cel Engine ainda (de propósito).

## Leia nesta ordem
1. [`docs/01-visao-geral-e-fluxo-de-dados.md`](docs/01-visao-geral-e-fluxo-de-dados.md) — modelo mental ROM → `.iso`
2. [`docs/02-pipeline-aot-pc.md`](docs/02-pipeline-aot-pc.md) — como achar código, separar dados, gerar o `.c`
3. [`docs/03-hle-suzy.md`](docs/03-hle-suzy.md) — Suzy → Cel Engine
4. [`docs/04-orcamento-memoria-2mb.md`](docs/04-orcamento-memoria-2mb.md) — cabe em 2 MB?
5. [`docs/05-riscos-e-decisoes-abertas.md`](docs/05-riscos-e-decisoes-abertas.md) — **decisões D1–D9 para aprovar**

## Estrutura
```
lynx23do/
├── docs/                    arquitetura (acima)
├── pc-tools/                roda NO PC (Python 3, só stdlib — decisão D1)
│   ├── lynx2c/              tradutor AOT: ingest → discover → lift → optimize → emit
│   ├── lynxtrace/           núcleo 65C02 de referência: perfil dinâmico + oráculo de testes
│   ├── spritecook/          sprites Suzy → dados de Cel (formato "packed" do 3DO) + PLUT
│   ├── pack3do/             Makefile do SDK, árvore do disco, ISO
│   └── tests/               testes diferenciais e de determinismo
├── runtime/                 código NATIVO (C89): 3DO e host
│   ├── include/lynx/        headers públicos (API do HLE, ABI do código gerado)
│   ├── src/                 núcleo portável (CPU ABI, overlays, Suzy, Mikey) — a implementar
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
```
O armcc/SDK 3DO **não** está disponível neste ambiente; a compatibilidade com o SDK
(assinaturas e formatos do CCB) está marcada `[VERIFY]` nos headers.

## Regras de trabalho
- **Backup antes de modificar** (`scripts/make_backup.sh`); backups nunca são alterados.
- Sem ROMs/BIOS no repositório (`.gitignore`).
- C89, big-endian-safe, sem interpretador em T3 (ver invariantes em `docs/01` §7).
