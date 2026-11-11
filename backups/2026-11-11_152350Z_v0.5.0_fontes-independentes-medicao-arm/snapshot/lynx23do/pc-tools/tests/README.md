# Testes do lado PC

```
pc-tools/tests/run_diff.sh                       # unitários + diferenciais, gcc C89 estrito, -O0 e -O2 (~45 s)
SKIP_UNIT=1 pc-tools/tests/run_diff.sh           # só os diferenciais
SKIP_UNIT=1 SKIP_BLOCKS=1 pc-tools/tests/run_diff.sh   # só programas (mutação rápida)
```
| Arquivo | Papel |
|---|---|
| `test_decode.py` | tabela do tradutor vs. tabela derivada do padrão de bits (49 opcodes); erros do decoder |
| `test_reference_core.py` | valida o oráculo: binário exaustivo, BCD válido por propriedade, ciclos, ZP wrap, semântica de fluxo à mão |
| `test_opt_emit.py` | vivacidade em bloco reto, classificação de região, C89, determinismo |
| `test_cfg.py` | CFG, líderes (vs. `independent.py`), erros explícitos, liveness entre blocos, ponto fixo, `precise_exits` |
| `independent.py` | líderes de bloco por algoritmo independente (oráculo do CFG) |
| `gen_vectors.py` + `harness/main.c` | corpus de BLOCOS RETOS: 557 mil vetores |
| `gen_programs.py` + `harness/main_prog.c` | corpus de PROGRAMAS (aleatórios + dirigidos) com o trampolim real: 9,7 mil vetores |
| `functional/run_dormann.sh` + `run_functional.py` + `functional_main.c` | suítes funcionais **independentes** de Klaus Dormann pelo pipeline completo, com sementes iterativas (`docs/08` §3) |
| `test_ingest.py`, `test_report.py` | estágio A (`.lnx`, BS93) e relatório/medição ARM |
| `test_handy_reference.py`, `test_handy_decimal.py` | comparação com o Handy: opcodes, ciclos-base e BCD exaustivo (A×M×C) |
| `harness/lx_test_stubs.c` | E/S falsa por chip (valor próprio por chip + detecção de roteamento errado) e agendador de teste |

Resultados, teste de mutação e limites: `docs/06` §3 e `docs/07` §5–6.
