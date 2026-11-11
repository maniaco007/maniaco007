# lynx2c — tradutor AOT 65C02 → C89

Especificação: [`docs/02-pipeline-aot-pc.md`](../../docs/02-pipeline-aot-pc.md) ·
estado atual: [`docs/06`](../../docs/06-traducao-lda-sta-adc-sbc.md).

**v0.2.0:** decode → lift → opt → emit para **LDA, STA, ADC, SBC** (blocos retos, 35 opcodes).

```
PYTHONPATH=pc-tools/lynx2c python3 -m lynx2c disasm    --org 0x0200 --hex "A9 01 69 02 8D 91 FC"
PYTHONPATH=pc-tools/lynx2c python3 -m lynx2c translate --org 0x0200 --hex "A9 01 69 02" --name lx_ov00_0200
```

| Módulo | Estágio | Estado |
|---|---|---|
| `optable.json` / `optable.py` | D | pronto (subconjunto; tabela é arquivo de dados) |
| `decode.py` | D | pronto (opcode fora da tabela = erro explícito) |
| `ir.py`, `lift.py` | D | pronto (defs/uses de flags, região do operando) |
| `opt.py` | E | vivacidade de flags em bloco reto; demais otimizações a fazer |
| `emit_c.py` | F | pronto p/ blocos retos (fase 1 do docs/02 §7) |
| `cli.py` | — | `disasm`, `translate` |
| `ingest`, `segments`, `discover`, `manifest` | A–C | **a fazer** |

Contrato com o runtime: `runtime/include/lynx/lx_cpu_abi.h` e `lx_overlay.h` (`LX_ABI_VERSION`,
conferido pelo C gerado). Saída determinística.
