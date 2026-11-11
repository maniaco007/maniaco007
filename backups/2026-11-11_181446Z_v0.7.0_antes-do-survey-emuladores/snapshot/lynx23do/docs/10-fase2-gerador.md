# 10 — Fase 2 do gerador: rotinas fundidas e registradores locais (v0.6.0)

Resposta ao achado de `docs/09`: a fase 1 gerava **27×** de código (11,1 ARM por instrução 65C02), o que deixava caber só ~23 KB de 65C02
em 640 KB. A fase 2 funde blocos em **rotinas** (uma função C por rotina, blocos ligados por `goto`) e mantém A/X/Y/S e os flags em
**variáveis locais**. Resultado medido: **17,9×–18,5× e 7,1 ARM por instrução** (−34%), com a mesma correção (Dormann + diferencial).

## 1. Desenho

```
CFG ─▶ partição em ROTINAS (routines.py) ─▶ emit_routine: um C por rotina
          raízes = entradas ∪ alvos de JSR ∪ continuações (JSR/BRK) ∪ blocos alcançados por ≥2 raízes
          + limite de blocos por rotina (padrão 32)
```
- **Rotina** = raiz + blocos alcançáveis por arestas *intra-rotina* (fall-through, desvio, `BRA`/`JMP abs`). `JSR`, `RTS`, `RTI`, `BRK` e
  `JMP` indireto **saem** da função (o trampolim despacha; `JSR` ainda empilha na pilha emulada — chamada C nativa é a fase 2b).
- **ABI v3**: `LxCodeFn(cpu, entry)`. `entry` escolhe o líder onde começar (0 = raiz). A tabela de despacho lista **todos os líderes**,
  cada um com `(função, sub-entrada)`, porque um `YIELD` no meio de uma rotina precisa ser retomado dali.
- **Variáveis locais**: carrega só o que a rotina usa, grava só o que ela escreve, numa única saída `L_exit`
  (`cpu->cycles = cyc; if (cyc >= ev) return lx_sched_service(cpu, pc); return pc;` — chamada final, sem quadro no caminho comum).
  Pilha e P usam macros sobre as locais (`LX_PUSH8/PULL8/PACK_P/UNPACK_P`); o decimal usa `lx_adc_dec_v/lx_sbc_dec_v` (retorno por valor,
  para não forçar as variáveis para a memória).
- **Teste de evento**: após **toda instrução de fluxo** (desvio tomado ou não, salto, `JSR`, `RTS`…) e em toda saída; **não** entre blocos
  que só caem um no outro. Cada teste custa `cmp`+`bhs` (a fase 1 pagava 11 instruções por bloco).

## 2. A regra de fronteira (o oráculo)
A referência para em *fronteiras*: instrução de fluxo, ou próximo PC que é **raiz** (início de função) ou sai da imagem. Em cada fronteira:
`ciclos ≥ orçamento ⇒ YIELD`; senão, `PC fora da tabela ⇒ não resolvido`. Na fase 1 raízes = todos os blocos; na fase 2 só as raízes das
rotinas. O tradutor expõe as raízes (`roots_of`); o gerador de programas usa **limites aleatórios** (0, 2, 3, 5, 8, 32) e **fase 1/2 misturadas**.

## 3. Bugs que o processo achou (vale registrar)
1. **Cair na raiz da própria rotina** (diferencial, 9 vetores em 2 de 232 programas): uma rotina pode ter blocos de endereço **menor** que a
   raiz; um deles pode cair fisicamente nela, e isso é fronteira para a referência. Eu havia argumentado que era impossível. Corrigido.
2. **Condição do desvio lendo `cpu->zsrc`** em vez da variável local (achado por **inspeção** do código gerado; o `-Werror` o barraria pela
   variável "carregada e não usada", mas só quando ela não é usada em outro lugar).
3. **Falso positivo no detector de trap** (65C02 estendida "falhou" em `$24F7`): na fase 2 os pontos de retomada só ocorrem em instruções de
   fluxo, então um laço longo que só muda a RAM cedia sempre no mesmo PC com os mesmos registradores. Trap agora exige **PC + registradores +
   hash da RAM de 64 KB** iguais em 3 cedimentos. Confirmado: passa nas duas fases e ainda detecta traps reais.

## 4. Medição (clang -Os → ARM big-endian; `tools/sweep_routines.py`)

| Dormann 6502 | rotinas | ARM total | expansão | ARM/instr | maior quadro de pilha |
|---|---:|---:|---:|---:|---:|
| fase 1 (ABI v2) | 2272 | 321 300 B | 26,9× | 11,1 | — |
| fase 2, **sem limite** | 39 | 303 224 B | 25,4× | 10,4 | **15 360 B** |
| fase 2, 64 blocos | 103 | 206 244 B | 17,2× | 6,9 | 44 B |
| fase 2, **32 blocos (padrão)** | 149 | 211 368 B | **17,7×** | **7,1** | **44 B** |
| fase 2, 16 blocos | 369 | 221 696 B | 18,5× | 7,4 | 44 B |
| fase 2, 8 / 4 / 2 blocos | 597 / 1044 / 1412 | 235 580 / 254 988 / 269 192 B | 19,7 / 21,3 / 22,5× | 8,0 / 8,7 / 9,2 | 44 B |

Resultado final com as sementes completas (`report.md`): **6502: 17,9× / 7,1 ARM·instr; 65C02: 18,5× / 7,1** (fase 1: 27,0× e 27,8×).

**Por que a fusão sozinha quase não ajudou** (25,4× vs 26,9×) **e o limite ajudou tanto:** em funções com dezenas de blocos as ~16 variáveis
vivas não cabem nos ~12 registradores do ARM: ~27% das instruções eram `str`/`ldr` de spill/reload e um quadro de **15 KB** (inviável numa
tarefa do 3DO). Escopos menores reduzem a pressão. A curva é rasa entre 16 e 64 blocos; 32 é o padrão.

## 5. Verificação
**114 unitários** (13 novos em `test_routines.py`: cada bloco em uma só rotina, raízes, divisão por limite, estrutura do C); diferencial de blocos
(895 632 vetores, agora pela **fase 2**) e de programas (10 240; 3/4 em fase 2 com limites variados); Dormann 6502 e 65C02 **passam nas duas fases**.
**Mutação** (10 mutantes válidos nas peças novas): cair na raiz sem teste, não gravar registradores, sub-entrada deslocada, saída sem serviço de
evento (não-terminação, pega pelo vigia), `LX_PULL8` sem incrementar S, `UNPACK_P` com V no bit errado, `PACK_P` com Z invertido… **todos detectados**
pelo diferencial; dois mutantes inválidos (erro de compilação) mostraram que o `-Werror` já barra variáveis carregadas e não usadas.

## 6. Limites e o que falta
- **17,9× ainda não é a meta de ≤10×.** Cabem ~36 KB de 65C02 em 640 KB (eram ~23 KB). Falta a **fase 2b**: `JSR` como chamada C nativa (hoje a
  continuação de um `JSR` inicia outra função e a chamada passa pelo trampolim), flags compactados para reduzir pressão, e forma *cold* para
  código frio guiada por perfil.
- Medição **estática** e de **clang −Os** (o armcc tende a gerar mais); desempenho em execução ainda não medido.
- `cpu->cycles` só é atualizado nas saídas: acessos a E/S no meio de uma rotina veem um contador atrasado (não importa até o Mikey real existir).
- O código do Dormann é favorável à fusão (rotinas enormes de código reto); jogos reais terão mais `JSR` e laços curtos — a fase 2b importa mais ali.

## 7. Próximos passos
1. **Fase 2b**: chamada nativa de `JSR`/retorno nativo de `RTS` (com a verificação do endereço desempilhado) e continuações dentro da função.
2. Agendador real (`lx_sched_service`), `WAI/STP`, `6502_interrupt_test`.
3. `lynxtrace` com perfil dinâmico para escolher o que vai para a forma *hot* e a *cold*.
