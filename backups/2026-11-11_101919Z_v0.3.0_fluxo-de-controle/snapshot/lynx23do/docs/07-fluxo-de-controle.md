# 07 — Fluxo de controle: Bcc, BRA, JMP, JSR, RTS (v0.3.0)

Soma-se aos 35 opcodes de `docs/06` mais **14**: `BPL BMI BVC BVS BCC BCS BNE BEQ BRA`, `JMP abs`,
`JMP (abs)`, `JMP (abs,X)`, `JSR`, `RTS` — **49 opcodes** no total.

## 1. O que mudou na arquitetura

```
bytes ─▶ build_cfg (descida recursiva, líderes) ─▶ lift ─▶ cfg_liveness (ponto fixo) ─▶ emit_overlay
                                                                                           │
                          lx_run (trampolim) ◀── tabela LxDispatchEntry ◀── uma função LxCodeFn por bloco
```

- **Bloco básico = uma função C** que devolve o **próximo PC** (fase 1 do `docs/02` §7). `lx_run` despacha
  pela tabela do overlay ativo (busca binária). Sem recursão no stack do ARM.
- **JSR/RTS usam a pilha EMULADA** ($0100–$01FF): `JSR` empilha o endereço do **último byte** do JSR (hi, depois lo);
  `RTS` desempilha lo, hi e soma 1. Por isso *RTS trick*, troca de pilha e retorno "errado" funcionam sem
  tratamento especial — o destino é só um PC a despachar.
- **PC sem código** → `lx_unresolved(pc)` registra e `lx_dispatch` devolve `LX_PC_HALT` (erro fatal *controlado*,
  não aborta o processo). Nunca "executa" bytes sem tradução.
- Fase 1 coloca **todo** bloco na tabela; a fase 2 reduzirá a alvos dinâmicos.

## 2. CFG (`cfg.py`)

- Líderes: entradas ∪ alvos de desvio/BRA/JMP/JSR ∪ instrução após desvio ∪ **continuação de JSR** (marcada
  `LX_DE_RETADDR`). Só o **alcançável** é decodificado: bytes não alcançados são dados.
- Erros **explícitos** (nada é podado em silêncio): opcode fora da tabela num caminho alcançável; instrução
  truncada no fim da imagem; **sobreposição** (desvio para o meio de uma instrução — salto desalinhado/SMC).
- Alvos fora da imagem são aceitos como saída externa (outro overlay ou dinâmico).
- Seeds extras (`--entry`) para alvos de `JMP` indireto/RTS trick vindos do perfil dinâmico ou do manifest.

## 3. Semântica

| Item | Decisão |
|---|---|
| Desvio | 2 ciclos; **+1 se tomado, +1 se o alvo cruza página** em relação à instrução seguinte (decidido na tradução) |
| `BRA` | 65C02; mesma regra de ciclos do desvio tomado |
| `JMP (abs)` | **65C02**: 6 ciclos e **sem** o bug de wrap de página do NMOS (`JMP ($10FF)` lê `$10FF` e `$1100`) — `[VERIFY]` no CPU do Lynx |
| `JMP (abs,X)` | 65C02; `ea = (abs+X) & $FFFF`; 6 ciclos |
| `JSR`/`RTS` | 6 ciclos cada; pilha emulada |
| Verificação de ciclos | `LX_SCHED_CHECK` ao fim de **todo** bloco, inclusive arestas de retorno (laços de espera por IRQ/vblank dependem disso) |

## 4. Vivacidade de flags entre blocos e a "pegadinha" do P

`cfg_liveness`: ponto fixo; `live_out` = união dos `live_in` dos sucessores estáticos; **todos vivos** se o fluxo sai
por RTS, `JMP` indireto, `JSR` ou alvo fora da imagem.

**Limite real, descoberto pelo teste diferencial:** com eliminação entre blocos, um flag morto numa fronteira pode
guardar valor **desatualizado** naquele ponto. O programa não vê (o código seguinte o redefine antes de ler), **mas um
IRQ entregue em `lx_sched_service` empilha o P a partir de `nsrc/zsrc/c/v`** — que pode divergir do hardware nos flags
mortos. Duas posições, ambas implementadas:

- **padrão (`precise_exits=False`)**: eliminação máxima; o P empilhado por IRQ pode divergir nos flags mortos.
  Jogos cujo handler de IRQ inspeciona o P empilhado precisam do modo preciso. `PHP` (futuro) declara `uses=NZCV`.
- **`--precise-exits`**: todo flag vivo em toda saída de bloco ⇒ P exato em qualquer ponto de IRQ; elimina só dentro
  do bloco. Seleção por jogo (manifest, futuro).

## 5. Verificação (`pc-tools/tests/run_diff.sh`, ≈ 45 s)

- **55 testes unitários**: tabela vs. derivada do padrão de bits (agora 49 opcodes); semântica de fluxo da referência
  verificada **à mão** (ciclos de desvio, pilha do JSR, wrap do `JMP (abs)`, `JMP (abs,X)`); CFG (líderes, dados não
  decodificados, erros explícitos, sobreposição, saída externa, determinismo); liveness (inclusive cadeia de 3 blocos que
  exige o ponto fixo, e `precise_exits`).
- **Diferencial de blocos retos**: 557 288 vetores (como em `docs/06`).
- **Diferencial de programas** (novo): **228 programas / 9 760 vetores** com o **trampolim real** (`lx_run`,
  `lx_dispatch`, `lx_overlay`), `-O0` e `-O2`: 220 aleatórios (8–48 instruções, org perto de limites de página, alvos
  externos, `JMP` indireto com tabela em RAM; 1/3 em modo `precise_exits`) + 8 dirigidos (laço com contador, sub-rotinas aninhadas, **RTS trick**,
  `JMP ($xxFF)`, desvios em limite de página, `JMP (abs,X)`). Mistura: 6 049 paradas por orçamento (YIELD) e 3 711 por PC
  não resolvido. Compara A X Y S P, ciclos, PC e razão da parada, escritas em RAM/E/S, roteamento de chip.
- A referência para exatamente onde o tradutor para; para não mascarar um líder esquecido, o gerador **exige** que os líderes
  do CFG coincidam com um algoritmo **independente** (`tests/independent.py`).

### Teste de mutação (manual, em cópias descartáveis) — 18 mutantes

| Mutante | Pego por |
|---|---|
| desvio sem o +1 de cruzamento de página | diferencial |
| desvio **não** tomado soma +1 | diferencial |
| `BNE` com condição invertida | diferencial |
| `JSR` empilha `addr+3`; empilha lo antes de hi | diferencial |
| `RTS` sem o +1; desempilha hi antes de lo | diferencial |
| `JMP (abs,X)` usa Y | diferencial |
| `JMP (abs)` com o bug de wrap do NMOS | diferencial (programa dirigido) |
| liveness: `BEQ` não "usa" Z | diferencial |
| CFG: sem líder após JSR / em alvo de BRA/JMP / sem dividir em líder | unitários **e** diferencial |
| busca binária do `lx_dispatch` ignora a última entrada | diferencial |
| ponto fixo de uma só passada | unitários **e** diferencial |
| `precise_exits` ignorado | unitários **e** diferencial |
| liveness: `JSR` não conservador | **equivalente** (o `RTS` já força "tudo vivo"; sem efeito observável) |

Os testes de mutação **expuseram fraquezas dos próprios testes**, corrigidas: (1) a referência herdava o conjunto de
entradas do tradutor e mascarava líderes esquecidos → oráculo independente de líderes; (2) a máscara de P vinha do tradutor
também no modo preciso → agora `0xFF` fixo; (3) teste do ponto fixo com distância curta demais → cadeia de 3 blocos.

## 6. Limites (leia antes de confiar)

- Oráculo escrito por nós ⇒ prova **consistência tradutor↔referência**, não fidelidade ao hardware. `[VERIFY]`: ciclos de
  `JMP (abs)`, `BRA`, `JMP (abs,X)` e o wrap do `JMP (abs)` no CPU **do Lynx**.
- Em modo padrão o P empilhado por IRQ pode divergir nos flags mortos (§4).
- Sem **SMC**: a referência busca instruções da imagem, o C não lê a RAM — escritas sobre o código são ignoradas por ambos.
- Ainda **sem** `RTI/BRK/PHP/PLP`, `INX/DEX…`, `CMP`, `AND/ORA/EOR`, `CLC/SEC/CLD/SED`: programas reais precisam deles
  (e para a suíte funcional independente tipo Klaus Dormann).
- `lx_sched_service` real (timers/IRQ) ainda não existe; os testes usam um agendador que só devolve `YIELD`.
- Desempenho: fase 1 (todo bloco passa pela tabela; busca binária por bloco). Sem medição.
- Nada compilado com o armcc do SDK 3DO.

## 7. Próximos passos sugeridos
1. Resto do conjunto "de uso comum" para programas reais: `CMP/CPX/CPY`, `AND/ORA/EOR`, `INC/DEC`, `INX/INY/DEX/DEY`,
   `LDX/LDY/STX/STY`, `Txx`, `PHA/PLA/PHP/PLP`, `CLC/SEC/CLD/SED/CLI/SEI/CLV`, `NOP`, `RTI/BRK` — com `PHP/PLP`
   exigindo flags exatos.
2. Com isso, rodar uma suíte funcional **independente** de 6502/65C02 (baixada pelo usuário) pelo pipeline completo.
3. `lynxtrace` com perfil dinâmico e estágios A–C (`ingest`, `discover`, `report.md` de elegibilidade).
