# lynx2c — tradutor AOT 65C02 → C89

Especificação: [`docs/02-pipeline-aot-pc.md`](../../docs/02-pipeline-aot-pc.md) · estado atual:
[`docs/06`](../../docs/06-traducao-lda-sta-adc-sbc.md), [`docs/07`](../../docs/07-fluxo-de-controle.md).

**v0.3.0:** decode → **CFG** → lift → **vivacidade de flags (ponto fixo)** → emit, para 49 opcodes:
LDA STA ADC SBC, Bcc/BRA, JMP (abs, (abs), (abs,X)), JSR, RTS.

```
export PYTHONPATH=pc-tools/lynx2c
python3 -m lynx2c disasm    --org 0x0200 --hex "A9 01 69 02 8D 91 FC"         # varredura linear (diagnóstico)
python3 -m lynx2c cfg       --org 0x0200 --hex "A9 01 20 0B 02 F0 02 69 02 60 EA 60"
python3 -m lynx2c translate --org 0x0200 --hex "A9 00 F0 02 69 01 60" [--entry 0x0210]... [--precise-exits]
```
`translate` emite um overlay completo (funções + tabela de despacho + `LxOverlay`).

| Módulo | Estágio | Estado |
|---|---|---|
| `optable.json` / `optable.py` | D | 49 opcodes, com `flow` (seq/branch/jump/jump_ind/call/ret) |
| `decode.py` | D | pronto (opcode fora da tabela = erro explícito; alvo estático dos desvios) |
| `cfg.py` | C | descida recursiva, líderes, erros explícitos (opcode, truncada, sobreposição) |
| `ir.py`, `lift.py` | D | defs/uses de flags, região do operando |
| `opt.py` | E | liveness em bloco e entre blocos; `precise_exits`; demais otimizações a fazer |
| `emit_c.py` | F | blocos + terminadores + tabela de despacho + overlay (fase 1, trampolim) |
| `pipeline.py`, `cli.py` | — | `analyze()`; `disasm`, `cfg`, `translate` |
| `ingest`, `segments`, `discover`, `manifest` | A–C | **a fazer** |

Contrato com o runtime: `runtime/include/lynx/lx_cpu_abi.h` e `lx_overlay.h` (`LX_ABI_VERSION`, conferido pelo C
gerado). Saída determinística.
