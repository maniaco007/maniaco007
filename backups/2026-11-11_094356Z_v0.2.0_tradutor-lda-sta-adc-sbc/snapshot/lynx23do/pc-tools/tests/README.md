# Testes do lado PC

```
pc-tools/tests/run_diff.sh              # unitários + corpus diferencial, gcc C89 estrito, -O0 e -O2
SKIP_UNIT=1 pc-tools/tests/run_diff.sh  # só o diferencial
```
| Arquivo | Papel |
|---|---|
| `test_decode.py` | tabela do tradutor vs. tabela derivada do padrão de bits; erros do decoder |
| `test_reference_core.py` | valida o oráculo: binário exaustivo, BCD válido por propriedade, ciclos, ZP wrap |
| `test_opt_emit.py` | vivacidade de flags, classificação de região, C89, determinismo |
| `gen_vectors.py` | gera `tests_gen.c` + `vectors.bin` (seed fixa) em `build/test/` |
| `harness/` | `main.c` (executa vetores), `lx_test_stubs.c` (E/S falsa por chip) |

Resultados e limites (o que **não** é provado): `docs/06` §3. Planejados: suítes funcionais independentes
(após fluxo de controle), jogo inteiro host-vs-referência, determinismo ponta a ponta.
