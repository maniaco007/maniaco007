# runtime/src — núcleo portável (3DO + host)

Arquivos planejados (nada implementado ainda); cada um realiza um header em `../include/lynx/`:

| Arquivo | Realiza | Conteúdo |
|---|---|---|
| `lx_alu.c` | `lx_alu.h` | **pronto:** ADC/SBC decimal (BCD) fora de linha |
| `lx_mem.c` | `lx_mem.h` | **pronto (parcial):** `lx_ram`, `lx_io_read/write`; MAPCTL/ROM de boot pendentes |
| `lx_sched.c` | `lx_cpu_abi.h` | `lx_sched_service`, timers do Mikey, IRQ, vblank |
| `lx_dispatch.c` | `lx_cpu_abi.h` | **pronto:** `lx_run` (trampolim), `lx_dispatch` (hook → tabela do overlay), `lx_unresolved` |
| `lx_overlay.c` | `lx_overlay.h` | **pronto (parcial):** overlays ativos, hooks, `lx_overlay_load`; cartucho serial (RCART) pendente |
| `lx_suzy.c` | `lx_suzy.h` | regs, `SPRGO`, decodificação de SCB, fila |
| `lx_suzy_map.c` | `lx_suzy.h`, `lx_cel.h` | SCB → `LxCelDesc`, PLUT, `LxViewXform` |
| `lx_suzy_soft.c` | `lx_suzy.h` | rasterizador de software (fallback XOR/sombra, `LX_FB_SOFT`, host) |
| `lx_suzy_coll.c` | `lx_suzy.h` | colisão BBOX/PIXEL |
| `lx_suzy_math.c` | `lx_suzy.h` | multiplicação/divisão do Suzy |
| `lx_mikey.c` | *(header futuro)* | timers, paleta, DMA de vídeo, UART, áudio (fase posterior) |

Regras: C89, sem `malloc` em laço quente, 16 bits = 2 bytes (3DO é big-endian).
