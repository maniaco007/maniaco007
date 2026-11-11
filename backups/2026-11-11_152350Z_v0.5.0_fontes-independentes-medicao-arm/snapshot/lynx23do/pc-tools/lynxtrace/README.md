# lynxtrace — núcleo 65C02 de referência (perfil dinâmico + oráculo)

Interpretador **no PC** (nunca vai para o 3DO). Dois papéis:

1. **Perfil dinâmico** (estágio B do `lynx2c`): executa o jogo headless com entradas
   gravadas e emite `trace.bin` — PCs executados e bytes buscados, alvos de salto
   indireto, `RTS` divergentes, carga de segmentos (leitura de `RCART0` → escrita em
   RAM), escritas no Suzy (SCB, `SPRDLINE`, `VIDBASE`), polling de E/S, contagem por bloco.
2. **Oráculo de testes**: estado (RAM + regs) por vblank para comparar com o código
   traduzido compilado no host (`docs/02` §9).

Também carrega a imagem de boot do Lynx **fornecida pelo usuário** (não distribuída aqui).
Escopo mínimo: só o necessário para trace e testes (decisão D9).

**v0.4.0:** `lynxtrace/core65c02.py` — oráculo de 178 opcodes, escrito de forma independente do tradutor (grupos regulares
derivados do padrão de bits `aaabbbcc`; desvios por `xxy10000`; ciclos por regras). `run_program()` executa imagens com a
mesma regra de parada em fronteira de bloco do código traduzido. Perfil dinâmico (`trace.bin`): a fazer.
