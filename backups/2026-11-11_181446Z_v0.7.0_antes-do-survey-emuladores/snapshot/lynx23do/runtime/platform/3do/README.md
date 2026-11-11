# platform/3do — backend 3DO

Implementa `lx_platform.h` com o SDK Portfolio (headers reais do trapexit/3do-devkit) e o fluxo do XProger/nes-3do (BSD-2-Clause).

| Arquivo | Papel |
|---|---|
| `lx_platform_3do.c` | vídeo (framebuffer do Lynx → Cel 4 bpp 2×), 2 buffers, VBL, pad, tempo, arquivo do CD |
| `lx_main_3do.c` | laço principal: `lx_machine_run_frame()` + `lx_machine_present()` |
| `Makefile` | `armcc → armlink → modbin → 3doiso → 3DOEncrypt`; `make host-check` roda o demo no PC sem o SDK |
| `NOTICE.md` | créditos e licenças |

**Estado:** verificado estaticamente contra os headers reais (`scripts/check_3do_build.sh`); **não compilado com o armcc, não executado**.
Passo a passo do primeiro teste e o que me enviar se falhar: **`docs/11-plataforma-3do-e-primeiro-teste.md` §6**.
