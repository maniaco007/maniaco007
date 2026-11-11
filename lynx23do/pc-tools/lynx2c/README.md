# lynx2c — tradutor AOT 65C02 → C89

Especificação: [`docs/02-pipeline-aot-pc.md`](../../docs/02-pipeline-aot-pc.md).
**Ainda sem código** (aguardando aprovação). Módulos planejados (um por estágio):

| Módulo | Estágio | Entrada → Saída |
|---|---|---|
| `ingest.py` | A | `.lnx` → `CartImage` (+SHA-256) |
| `segments.py` | B/C | `trace.bin` + manifest → overlays `(cart_offset, load_addr, len)` |
| `discover.py` | C | overlays + seeds → `cfg.json`, `classmap.bin`, `report.md` |
| `decode.py` / `optable.*` | D | bytes → `Insn` (**próxima etapa**: tabela em arquivo de dados) |
| `lift.py` | D | `Insn` → IR (micro-ops com `defs/uses` de flags, região, ciclos) |
| `opt/` | E | vivacidade de flags, regiões, constantes, hot/cold, rotinas |
| `emit_c.py` | F | IR → `gen/*.c`, `lx_tables.c`, `lx_program.c`, `lx_game_config.h` |
| `manifest.py` | — | valida `games/<jogo>/manifest.toml` |
| `cli.py` | — | `lynx2c analyze|translate|report|--seed unresolved.log` |

Contrato com o runtime: `runtime/include/lynx/lx_cpu_abi.h` e `lx_overlay.h`
(`LX_ABI_VERSION`). Saída **determinística** (ordenar por `(overlay, addr)`).
