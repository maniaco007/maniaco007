# 11 — Plataforma 3DO: o que foi reaproveitado, o que foi verificado e como fazer o primeiro teste (v0.7.0)

## 1. O que existe no GitHub e o que reaproveitei

| Repositório | Licença | O que é | Uso |
|---|---|---|---|
| **trapexit/3do-devkit** | não declarada | devkit moderno: Norcroft ARM C 4.91 (**armcc original, Linux e Windows**), headers e libs do Portfolio 2.5, `modbin`, `3doiso`, docs do SDK, exemplos | **referência e ferramenta do SEU PC**: li os headers para eliminar os `[VERIFY]`; o Makefile o usa pelo caminho `DEVKIT=`. **Nada dele é copiado para este repositório** |
| **XProger/nes-3do** | BSD-2-Clause | emulador de NES para 3DO (roda em hardware) | modelo funcional de inicialização, laço de quadro, pad, CD e Makefile (`armcc → armlink → modbin → 3doiso → 3DOEncrypt`); código **reescrito**, créditos em `runtime/platform/3do/NOTICE.md` |
| **libretro/opera-libretro**, **tordona/4DO** (GPL-2.0), FreeDO | — | emuladores de 3DO | **não executados**: precisam da BIOS do 3DO (a sua) e a execução de binários baixados exige a sua autorização (ver §5) |
| **Handy** (libretro-handy) | zlib | emulador de Lynx | layout de paleta/vídeo/joystick do Mikey/Suzy (dado de referência) |
| vs-sr-dev/3dokit (MIT) | MIT | "toolkit para portes de 3DO, … ARM60 …" | **não avaliado ainda** |

Descartado de propósito: o `cpu_op.s` do nes-3do (interpretador de 6502 em assembly ARM) — o nosso desenho é recompilação estática.

## 2. Fatos conferidos nas fontes (eliminam `[VERIFY]`)

| Fato | Fonte |
|---|---|
| Campos do CCB: `Flags, NextPtr, SourcePtr, PLUTPtr, XPos, YPos, HDX, HDY, VDX, VDY, HDDX, HDDY, PIXC, PRE0, PRE1, Width, Height` — **idênticos ao `LxCelDesc`** | `graphics_ccb.h` |
| `CCB_SKIP=$80000000, LAST=$40000000, NPABS=$20000000, SPABS=$10000000, PPABS=$08000000, LDSIZE, LDPRS, LDPPMP, LDPLUT=$00800000, CCBPRE, YOXY, ACSC, ALSC, ACW, ACCW, ACE, PACKED=$200, BGND=$20, NOBLK=$10` | `graphics.h` |
| `PRE0_BPP_4 = 3` (4 bpp codificado), `PRE0_BGND`, `PRE1_TLLSB_PDC0` ("Normal") | `graphics.h` |
| **Ponto fixo**: `HDX = 1<<20` (12.20), `VDY = 1<<16` (16.16), `XPos = x<<16` — as **duas** fontes (SDK e nes-3do) concordam com o que eu assumira | `nes-3do/main.c` |
| RGB555 do 3DO: `MakeRGB15(r,g,b) = (r<<10)\|(g<<5)\|b` | `graphics.h` |
| `CreateCel(w,h,bpp,CREATECEL_CODED,buf)`, `CreateBackdropCel`, `DrawScreenCels(Item, CCB*)`, `DisplayScreen`, `WaitVBL`, `GetControlPad`, `OpenDiskStream` | headers do SDK |
| Mikey: `GREENn` = nibble baixo; `BLUEREDn` = **azul no nibble alto, vermelho no baixo**; `DISPADR=$FD94/95`, `DISPCTL=$FD92`; pixel da **esquerda = nibble ALTO** (igual ao 4 bpp do 3DO) | Handy `mikie.cpp` |
| JOYSTICK `$FCB0`: b7 Up, b6 Down, b5 Left, b4 Right, b3 Opção 1, b2 Opção 2, b1 Inside, b0 Outside; SWITCHES `$FCB1` b0 Pause | Handy `susie.h` |
| BS93: `80 08` (BRA +8: cabeçalho executável), `load_address` e `size` big-endian, arquivo inteiro em `load_address−10` | Handy `ram.cpp` |
| O disco precisa do esqueleto `takeme/` do devkit (`System/`, `rom_tags`, `signatures`) | devkit, nes-3do |

## 3. O que foi construído nesta versão

- `lx_video.c` — paleta e DMA de vídeo do Mikey, **independente de plataforma** (teste em C no host).
- `lx_machine.c` — agendador **mínimo** (1 quadro = 66 667 ciclos), `lx_machine_present()`, `lx_resume_pc`.
- `lx_mikey.c`, `lx_suzy_min.c` — registradores mínimos: vídeo real; JOYSTICK/SWITCHES da plataforma; `SPRGO` **contado e ignorado**.
- **Backend de host** (`lx_platform_host.c`, grava PPM) — permite o **teste de ponta a ponta no PC**.
- **Backend 3DO** (`lx_platform_3do.c`, `lx_main_3do.c`, `Makefile`): framebuffer do Lynx → Cel codificado 4 bpp 2× (320×204 centrado), fundo preto por `CreateBackdropCel`, 2 buffers, VBL 60 Hz, pad, tempo, arquivo.
- `lynx2c build` — BS93 → `*_gen.c` (rotinas + `lx_program`) e `*_image.c` (imagem de RAM).
- `games/demo_bars` — homebrew 65C02 de teste: programa a paleta pelos registradores, preenche o framebuffer (16 barras), liga o DMA e lê o joystick.
- `scripts/check_3do_build.sh` — verificação estática (ver §4).

## 4. Verificação feita aqui

| Verificação | Resultado |
|---|---|
| `test_video.c` (paleta, expansão 4→5 bits, DISPADR, DISPCTL) | passa |
| **Ponta a ponta no PC**: demo 65C02 → tradutor → runtime → Mikey → PPM, comparado com imagem **esperada calculada em Python de forma independente**; fases 1 e 2, `-O0` e `-O2`, 3 valores de joystick | **passa nas 4 configurações** |
| Runtime + jogo gerado como **ARM big-endian**, C89 estrito (`-Werror`), com o `string.h` do SDK | passa (`demo_gen.o`: 1 001 bytes de `.text`) |
| Backend 3DO contra os **headers reais do SDK** (declaração implícita, ponteiro incompatível e campo inexistente = erro) | passa; **3 erros injetados foram detectados** (sensibilidade provada) |

**Limites desta verificação:** o clang não é o armcc; nada foi compilado com o `armcc`, linkado, convertido por `modbin`, empacotado em ISO, nem executado em emulador ou no console.

## 5. O que NÃO consegui fazer, e por quê
O classificador de segurança do ambiente **bloqueou a execução do `armcc`** (e do `source activate-env`) por serem binários pré-compilados de um repositório de terceiros. Não contornei. Duas saídas:
1. **você compila no seu PC** (instruções abaixo; é o caminho que recomendo para o primeiro teste: o resultado real vem de você de qualquer jeito, no ODE);
2. você autoriza explicitamente a execução do `armcc` do devkit neste ambiente (aí eu compilo e linko aqui e ajusto erros antes de você tocar no console). Emuladores (Opera/4DO) também exigiriam isso **e** a BIOS do 3DO, que eu não tenho.

## 6. Como fazer o primeiro teste (M1) no SEU PC

```bash
cd 3do-devkit && source ./activate-env            # (Windows: activate-env.bat)  -> armcc, armlink, modbin, 3doiso, 3DOEncrypt no PATH
cd <repo>/lynx23do/runtime/platform/3do
make host-check                                    # confere o demo no PC (sem o SDK): deve imprimir "quadros=8 sprgo_ignorados=0"
make DEVKIT=/caminho/3do-devkit                    # gera _build/CD/LaunchMe e lynx23do.iso
```
Copie `lynx23do.iso` para o ODE. **Resultado esperado:** 16 barras verticais de cores (do vermelho ao azul/verde), 320×204 centradas
na tela com faixas pretas em cima e embaixo; **os dois primeiros pixels** da primeira linha (canto superior esquerdo) mudam de cor ao
apertar botões (eles mostram o byte do joystick).

**Se algo falhar, me envie:** (a) o log completo do `make` (a primeira mensagem de erro do `armcc`/`armlink` basta); (b) se compilou:
o que a tela mostrou (preta, travada, barras erradas, cores trocadas) e se o `printf` aparece no seu depurador/ODE. Cada sintoma tem
uma causa provável diferente: tela preta → `CreateCel`/`PLUT`; cores trocadas → ordem RGB; barras deslocadas → `PRE1`/largura da linha;
travada → `WaitVBL` ou pilha.

## 7. Estimativa de tempo, atualizada
O M1 deixou de ser "a escrever" e passou a **"escrito e verificado estaticamente, falta rodar"**. Se o `make` do seu PC compilar de
primeira, o M1 acontece **no mesmo dia em que você rodar**; é comum haver 1–3 rodadas de ajuste (erros do armcc, ISO que o ODE não
aceita, PLUT). Os marcos seguintes continuam como em `docs/` anteriores: **M2** (Mikey com timers/IRQ e vblank por interrupção) é o
próximo trabalho de verdade; **M3** (sprites do Suzy) o maior. **Um jogo comercial segue sem previsão** (precisa da ROM de boot sua e
do `lynxtrace` dinâmico).

## 8. Limites do estado atual
Sem timers/IRQ do Mikey, sem áudio, sem Suzy (sprites, matemática, colisão), sem cartucho serial: a maioria dos jogos **ainda não roda**.
Funciona um homebrew que desenha por CPU e faz polling. A fase 2b (`JSR` nativo), o desempenho real no ARM60 (nunca medido) e a ordem de
bytes **executando** em big-endian (só compilada) seguem abertos.
