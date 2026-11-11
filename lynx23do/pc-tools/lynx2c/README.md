# lynx2c — tradutor AOT 65C02 → C89

Especificação: [`docs/02-pipeline-aot-pc.md`](../../docs/02-pipeline-aot-pc.md) · estado atual:
[`docs/06`](../../docs/06-traducao-lda-sta-adc-sbc.md), [`docs/07`](../../docs/07-fluxo-de-controle.md).

**v0.4.0:** decode → **CFG** → lift → **vivacidade de flags (ponto fixo)** → emit, para **178 opcodes** (NMOS documentados +
65C02 de uso comum; sem Rockwell/WDC). Suporta `--smc-operand` (operando imediato modificável), `--hook`, `--precise-exits`.
Tabela gerada por `tools/gen_optable.py`.

```
export PYTHONPATH=pc-tools/lynx2c
python3 -m lynx2c disasm    --org 0x0200 --hex "A9 01 69 02 8D 91 FC"         # varredura linear (diagnóstico)
python3 -m lynx2c cfg       --org 0x0200 --hex "A9 01 20 0B 02 F0 02 69 02 60 EA 60"
python3 -m lynx2c translate --org 0x0200 --hex "A9 00 F0 02 69 01 60" [--entry 0x0210]... [--precise-exits]
```
`translate` emite um overlay completo (funções + tabela de despacho + `LxOverlay`).

| Módulo | Estágio | Estado |
|---|---|---|
| `optable.json` / `optable.py` | D | 178 opcodes, com `flow` (seq/branch/jump/jump_ind/call/ret/brk); gerada por `tools/gen_optable.py` |
| `decode.py` | D | pronto (opcode fora da tabela = erro explícito; alvo estático dos desvios) |
| `cfg.py` | C | descida recursiva, líderes, erros explícitos (opcode, truncada, sobreposição, SMC), hooks e `param_operand` |
| `ir.py`, `lift.py` | D | defs/uses de flags, região do operando |
| `opt.py` | E | liveness em bloco e entre blocos; `precise_exits`; demais otimizações a fazer |
| `emit_c.py` | F | blocos + terminadores + tabela de despacho + overlay (fase 1, trampolim) |
| `pipeline.py`, `cli.py` | — | `analyze()`; `disasm`, `cfg`, `translate` |
| `ingest`, `segments`, `discover`, `manifest` | A–C | **a fazer** |

Contrato com o runtime: `runtime/include/lynx/lx_cpu_abi.h` e `lx_overlay.h` (`LX_ABI_VERSION`, conferido pelo C
gerado). Saída determinística.
