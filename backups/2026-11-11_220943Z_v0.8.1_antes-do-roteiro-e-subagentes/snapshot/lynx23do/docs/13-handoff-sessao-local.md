# 13 — Handoff para a sessão local (PC do usuário)

Gerado ao fim da sessão em nuvem (v0.8.0). Objetivo: o Claude Code **local** retomar daqui sem perder contexto, com acesso ao disco do PC,
ao devkit do 3DO (`armcc`) e aos projetos NES→3DO e Master System→3DO.

## 1. Como baixar e conferir (5 minutos)
```bash
git clone https://github.com/<dono>/<repo>.git && cd <repo>
git checkout ccr-f44b572a-gwjotv          # se estiver usando o repositório original (branch de trabalho); no repositório exportado já é a main
export PYTHONPATH=$PWD/lynx23do/pc-tools/lynx2c:$PWD/lynx23do/pc-tools/lynxtrace:$PWD/lynx23do/pc-tools/tests
python3 -m unittest discover -s lynx23do/pc-tools/tests -p 'test_*.py'     # esperado: Ran 149 tests ... OK
lynx23do/pc-tools/tests/run_diff.sh                                         # esperado: 0 falhas em -O0 e -O2 (~80 s)
scripts/check_backups_immutable.sh                                          # esperado: OK
cd <pasta-do-projeto> && claude                                             # abre o Claude Code local; ele lê o CLAUDE.md da raiz
```
Resultados de referência (v0.8.0, medidos na nuvem): 149 unitários OK; diferencial **909 852** vetores de blocos + **13 920** de programas, 0 falhas
(`-O0`/`-O2`, fases 1 e 2); Dormann 6502 e 65C02 passam; 6/6 mutantes dos recursos novos mortos. Se algo divergir no PC (versão de gcc/python), isso é informação útil.

## 2. O que existe (resumo; detalhes em `docs/01`–`docs/12`)
| Parte | Estado |
|---|---|
| Tradutor `lynx2c` (65C02 → C89): decoder, CFG, flags preguiçosos, vivacidade, fase 2 (rotinas fundidas), 3 modelos de CPU | **pronto e verificado** |
| Oráculo `lynxtrace/core65c02.py` independente; Dormann; Handy/Gearlynx como fontes externas; mutação | **pronto** |
| Runtime portável (`lx_mem`, `lx_dispatch`, `lx_overlay`, `lx_alu`, `lx_video`, `lx_mikey`/`lx_suzy_min` mínimos, `lx_machine`) | **M1 mínimo**: sem timers/IRQ, sem Suzy, sem áudio |
| Backend host (PPM) e demo `games/demo_bars` ponta a ponta no PC | **pronto** |
| Backend 3DO (`runtime/platform/3do`) | **escrito, verificado estaticamente vs. headers reais; NUNCA compilado com `armcc` nem executado** |
| `ingest`: `.lnx`, LNX2, BS93, imagem plana | pronto; **jogo comercial exige HLE do boot** (docs/12 §6, a fazer) |
| Medidas: expansão 27× (fase 1) → 17,9× (fase 2), ~7,1 ARM/instr; ~35 KB de 65C02 cabem em 640 KB | estático; **desempenho dinâmico no ARM60 nunca medido** |

## 3. O que NÃO está feito (honesto)
- Nada rodou em hardware 3DO nem em emulador 3DO; ordem de bytes big-endian só **compilada** (host é little-endian).
- Mikey: sem timers/IRQ/vblank por interrupção, sem áudio, sem UART, sem EEPROM. Suzy: sem sprites/colisão/matemática. Sem cartucho serial (RCART).
- Temporização usa constante provisória (66 667 ciclos/quadro); o modelo real (ticks de 16 MHz, busca 4 / dado 5; quadro dirigido por timers 0/2) está em docs/12 §3–4, não implementado.
- Fase 2b (`JSR`/`RTS` nativos), `lynxtrace` com perfil dinâmico.
- Nenhum jogo comercial testado; nenhum Lynx II real testado (Rockwell implementado e testado por oráculo, não por jogo).

## 4. O que o Claude local pode fazer e a nuvem não podia
1. **Rodar o `armcc`** do devkit (`source ./activate-env` no `3do-devkit`) e compilar `runtime/platform/3do` (`make DEVKIT=...`). Foi a barreira da nuvem.
2. Ler as pastas **NES→3DO** e **Master System→3DO** do usuário (já funcionam no console dele) e dizer o que reaproveitar.
3. Gerar o ISO e testar no ODE com o usuário (resultado esperado: docs/11 §6).

## 5. Roteiro sugerido para a primeira sessão local
**A. Avaliar os dois projetos do usuário (NES e Master System), SOMENTE LEITURA.** Para cada um, registrar em um novo `docs/14-avaliacao-projetos-nes-sms.md`:
 1. Tipo: porte por recompilação, emulador interpretado ou código reescrito? Linguagem(ns) e tamanho.
 2. **Cadeia de build e ISO que o ODE aceita**: compilador/flags, `modbin`, `3doiso`, `3DOEncrypt`, árvore do disco (`LaunchMe`, `takeme`...), estrutura do `Makefile`.
 3. **Vídeo**: como desenha (Cels, `DrawScreenCels`, framebuffer direto?), resolução, formato de pixel/PLUT, dupla bufferização, sincronismo (`WaitVBL`).
 4. **Entrada** (`GetControlPad`/EventBroker), **áudio** (audio folio/DSP/SPORT), temporização (como fixa a taxa), uso de memória (2 MB / VRAM).
 5. **Desempenho medido** no console real (fps por jogo) e gargalos conhecidos.
 6. O que é **reaproveitável** no `lynx23do` (backend de plataforma `lx_platform.h`, ISO, áudio, entrada) e o que é específico do console.
 7. Licenças/créditos de código de terceiros dentro deles (para `NOTICE`).
 Não copiar nada para o repositório sem o usuário confirmar a licença.
**B. Primeiro teste M1 no console**: docs/11 §6. Se o `armcc` falhar, a **primeira mensagem de erro** diz qual hipótese do backend estava errada
 (sintomas e causas prováveis estão em docs/11 §6). Corrigir o backend; reexecutar `scripts/check_3do_build.sh`.
**C. M2** (docs/12 §3–4): ticks, timers do Mikey, IRQ por nível, vblank real, agendador por próximo evento, `CPUSLEEP`. Cada passo com oráculo + diferencial + mutação.
**D. Depois**: HLE do boot e `ingest` comercial; M3 (Suzy: oráculo de sprites a partir da especificação do Felix em docs/12 §5); áudio; EEPROM.

## 6. Perguntas em aberto para o usuário (responder na sessão local)
- Quais jogos Lynx são o alvo? (Define o que M2/M3 priorizam; jogos com SMC ou código gerado em RAM exigem hooks.)
- Meta de desempenho no ARM60: aceitar menos de 60 fps? (O custo real do código traduzido ainda não foi medido.)
- Como o usuário gerou o ISO que o ODE aceitou (receita exata)? Evita retrabalho no `Makefile` do backend.
- Cartuchos > ~384 KB: rejeitar (decisão D8 atual) ou fazer *streaming* do CD?

## 7. Referências externas usadas (não incluídas no repositório)
Clonadas na nuvem em modo leitura; reclonar no PC se quiser consultar: `laoo/Felix` (`f5a9cda`), `drhelius/Gearlynx` (`94068da`, GPLv3),
`libretro/libretro-handy` (`bc55d46`), `geo-tp/Cardputer-Game-Station-Emulators` (`74b4776`), `trapexit/3do-devkit` (`e997dc3`), `XProger/nes-3do` (`92bcdd0`).
Para refazer a conferência de ciclos: `python3 lynx23do/pc-tools/lynx2c/tools/crosscheck_gearlynx.py <Gearlynx>/src/m6502_timing.h` (esperado: 0 divergências).

## 8. Regras de trabalho (resumo; texto completo em `CLAUDE.md`)
Backup imutável com README antes de qualquer modificação (`scripts/make_backup.sh`), nunca mexer em `backups/`, português, C89, sem ROMs no repositório,
nada afirmado sem medição, todo teste novo precisa falhar quando o código está errado.
