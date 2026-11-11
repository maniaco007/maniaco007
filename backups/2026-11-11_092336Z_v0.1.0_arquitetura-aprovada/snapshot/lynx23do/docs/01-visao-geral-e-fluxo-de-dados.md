# 01 — Visão geral e fluxo de dados

> Estágio: **arquitetura (v0.1.0) — aguardando aprovação**. Nenhum tradutor de
> opcodes nem código de inicialização do Cel Engine foi escrito.

## 1. Premissa

O Lynx (65C02 @ 4 MHz) é emulável em um 3DO (ARM60 @ 12,5 MHz) só se **não
interpretarmos**. Um interpretador de 65C02 gasta ~30–60 instruções ARM por
instrução emulada; o orçamento é ~6 (§6). Por isso o sistema é **híbrido**:

| Parte do Lynx | Técnica | Onde roda |
|---|---|---|
| CPU 65C02 | **Recompilação estática (AOT)** → C89 | tradução no PC; resultado compilado pelo armcc |
| Suzy (sprites, escala, tilt) | **HLE** → `DrawCels()` do Cel Engine | runtime 3DO |
| Suzy (matemática, cartucho, joystick) | HLE em C (pequeno) | runtime 3DO |
| Mikey (timers, vídeo DMA, paleta, áudio) | HLE em C, dirigido por contador de ciclos | runtime 3DO |

## 2. Três tempos

```
 T1  TEMPO DE TRADUÇÃO (PC, offline)     lynx2c, lynxtrace, spritecook, pack3do
 T2  TEMPO DE BUILD   (PC, SDK 3DO)      armcc/armlink -> executável 3DO -> ISO
 T3  TEMPO DE EXECUÇÃO (3DO)             runtime + código gerado + dados cozidos
```

Tudo que puder ser decidido em T1 **não** é decidido em T3 (classificação de
código/dado, região de memória de cada acesso, custo em ciclos de cada bloco,
flags mortos, formato dos sprites).

## 3. Fluxo ponta a ponta (ROM → .iso)

```
 jogo.lnx ─────────┐
 manifest.toml ────┤                      PC (Python)
 replay de entrada ┤
                   ▼
        ┌──────────────────┐   ┌──────────────────┐
        │ A. ingest        │──▶│ B. lynxtrace     │  executa a ROM num núcleo de
        │ cabeçalho .lnx,  │   │ (núcleo de       │  referência (headless) e grava
        │ CartImage, SHA   │   │ referência)      │  o PERFIL DINÂMICO (trace.bin)
        └──────────────────┘   └────────┬─────────┘
                                        ▼
                         ┌──────────────────────────┐
                         │ C. discover              │  descoberta de overlays, descida
                         │ (CFG + classificação     │  recursiva a partir de seeds,
                         │  código/dado)            │  classmap + cfg.json + report.md
                         └────────────┬─────────────┘
                                      ▼
                         ┌──────────────────────────┐
                         │ D. lift  → IR            │  65C02 -> micro-ops com flags
                         │ E. optimize              │  explícitos; vivacidade de flags;
                         │                          │  regiões; hot/cold; rotinas
                         └────────────┬─────────────┘
                                      ▼
        ┌─────────────────────────┐  ┌──────────────────────────┐
        │ F. emit C89             │  │ G. spritecook            │ SCB/sprite Lynx
        │ gen/*.c, lx_program.c   │  │ sprites -> Cel "packed"  │ -> dados do Cel
        │ gen/lx_game_config.h    │  │ lxdata.bin + índice      │ Engine (3DO)
        └───────────┬─────────────┘  └────────────┬─────────────┘
                    └───────────────┬─────────────┘
                                    ▼
                         ┌──────────────────────────┐
                         │ H. pack3do               │  makefile do SDK, árvore de
                         │                          │  arquivos do disco, ISO
                         └────────────┬─────────────┘
                                      ▼
   runtime/ (C89) + gen/*.c ──armcc/armlink──▶ executável ──▶ ISO (Opera FS) ──▶ 3DO
                                      │
                       (mesma fonte, alvo LX_TARGET_HOST)
                                      ▼
                  binário de PC p/ teste diferencial vs. núcleo de referência
```

Artefatos por jogo em `build/<jogo>/` (ignorado pelo git; **saída determinística**:
mesmas entradas → mesmos bytes):

```
build/<jogo>/analysis/  trace.bin  cfg.json  classmap.bin  report.md  unresolved.json
build/<jogo>/gen/       lx_ov00_0000.c ...  lx_tables.c  lx_program.c  lx_game_config.h  game.map
build/<jogo>/data/      lxdata.bin  lxdata.idx          (cartucho + sprites cozidos)
build/<jogo>/3do/       Makefile  files/  <jogo>.iso
```

## 4. Fluxo de dados em tempo de execução (por frame do 3DO)

```
 lx_run(cpu, pc)                         laço principal (1x por frame)
   │
   ├─▶ bloco/rotina traduzida ──soma ciclos──▶ LX_SCHED_CHECK ──▶ lx_sched_service()
   │        │                                                     ├ timers Mikey (hblank/vblank)
   │        │ escreve $FCxx/$FDxx                                 ├ IRQ → vetor ($FFFE)
   │        ▼                                                     └ SPRSYS busy / vblank
   │   lx_suzy_write / lx_mikey_write
   │        │ SPRGO
   │        ▼
   │   lx_suzy_sprgo ─▶ SCB→Cel ─▶ fila ─┐
   │                                      │ flip de buffer / vblank / fb lido
   │                                      ▼
   │                           lx_suzy_flush ─▶ lx_gfx_submit_cels ─▶ DrawCels (Cel Engine, VRAM)
   │
   └─▶ LX_PC_YIELD (frame completo) ─▶ lx_gfx_present ─▶ lê pad ─▶ próximo frame
```

## 5. Responsabilidades

| Componente | Tempo | Entrada | Saída |
|---|---|---|---|
| `pc-tools/lynx2c` | T1 | `.lnx`, manifest, trace | `.c` gerado, cfg, relatório |
| `pc-tools/lynxtrace` | T1 | `.lnx`, replay | `trace.bin` (perfil dinâmico) e núcleo de referência p/ testes |
| `pc-tools/spritecook` | T1 | SCBs/sprites achados no trace | dados de Cel "packed" + PLUT |
| `pc-tools/pack3do` | T1→T2 | gen/, data/, runtime/ | Makefile, árvore do disco, ISO |
| `runtime/src` (núcleo) | T3 | — | ABI da CPU, overlays, HLE Suzy/Mikey (igual em 3DO e host) |
| `runtime/platform/3do` | T3 | — | `DrawCels`, VRAM, pad, CD |
| `runtime/platform/host` | T3 (PC) | — | rasterizador de software p/ testes |

## 6. Orçamento de CPU (conta de padeiro — **a validar em medição**)

- 65C02 @ 4 MHz com ~3,5 ciclos/instr ≈ **1,1 M instruções/s**.
- ARM60 @ 12,5 MHz, **sem cache**, DRAM compartilhada: assumir ≤ ~60–70 % útil
  para o código traduzido (resto: HLE, áudio, Cel Engine disputando barramento)
  ⇒ ~8 M ciclos/s úteis ⇒ **~7 ciclos ARM por instrução 65C02** no teto.
- Meta de projeto: **≤ 6 instruções ARM por instrução 65C02 na média**. Só é
  possível com: flags preguiçosos + análise de vivacidade; regiões resolvidas
  em T1; registradores A/X/Y/S em registradores ARM dentro de uma rotina;
  contabilidade de ciclos em blocos, não por instrução.
- Ponto a favor: no Lynx, **a CPU fica parada enquanto o Suzy desenha**; no 3DO o
  Cel Engine desenha em paralelo — o desenho deixa de custar tempo de CPU.
- Ponto contra: o 3DO tem que desenhar a 320×240 com *fill rate* finito; muitos
  sprites grandes escalados podem saturar o Cel Engine (medir cedo).

## 7. Invariantes do projeto

1. **C89** em todo código do runtime e gerado (armcc do SDK 3DO).
2. **Big-endian no 3DO**: RAM Lynx é `lx_u8[65536]`; 16 bits = 2 acessos de 8.
3. **Sem interpretador em T3**; PC sem tradução → `lx_unresolved()` + relatório.
4. **Mesma fonte, dois alvos** (3DO e host) → teste diferencial no PC.
5. **Sem ROMs/BIOS no repositório** (`.gitignore`); o usuário fornece os seus.
6. **Determinismo** das saídas do tradutor.
7. **Backups imutáveis** em `backups/` (ver `scripts/`).
