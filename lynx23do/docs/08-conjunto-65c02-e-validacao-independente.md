# 08 — Conjunto 65C02 completo de uso comum e validação independente (v0.4.0)

Soma-se aos 49 opcodes de `docs/06`–`07` mais **129**, totalizando **178**: todos os opcodes **NMOS documentados** e as
extensões 65C02 de uso geral. É o conjunto que roda a suíte funcional de Klaus Dormann sem alterações no tradutor.

## 1. Opcodes

| Grupo | Opcodes |
|---|---|
| ALU grupo 1 (9 modos, inclui `(zp)`) | `ORA AND EOR CMP` (somam-se a `LDA STA ADC SBC`) |
| Testes de bits | `BIT` (zp, zp,X, abs, abs,X, **#imm** — 65C02), `TSB TRB` (65C02) |
| Registradores X/Y/zero | `LDX LDY STX STY STZ`(65C02) `CPX CPY` — modo novo `zp,Y` |
| Leitura-modificação-escrita | `INC DEC ASL LSR ROL ROR` (acumulador e memória; `INC A`/`DEC A` são 65C02) |
| Implícitos | `INX INY DEX DEY TAX TXA TAY TYA TSX TXS CLC SEC CLI SEI CLV CLD SED NOP` |
| Pilha | `PHA PLA PHP PLP`, `PHX PLX PHY PLY` (65C02) |
| Interrupção | `BRK` (2 bytes), `RTI` |

> **Nota (v0.8.0, `docs/12` §2–2.1):** esta página descreve o conjunto **core** (178). Desde a v0.8.0 o `lynx2c` também decodifica, por modelo
> (`--cpu lynx1` padrão | `lynx2` | `core` estrito), os NOPs indocumentados (`CB`/`DB` incluídos) e, no Lynx II, `RMB/SMB/BBR/BBS`. Tabelas conferidas contra o Gearlynx: 0 divergências.

**Fora do conjunto, de propósito** (decoder rejeita com erro explícito): `BBR/BBS/RMB/SMB` (Rockwell), `WAI/STP` (WDC),
NOPs indefinidos de 2/3 bytes. `[VERIFY]` se o CPU do Lynx os tem.

## 2. Decisões de semântica novas

- **Flag B** só existe no P *empilhado*: `PHP` e `BRK` empilham B=1 (e o bit 5); `PLP`/`RTI` o ignoram; internamente fica 0.
- **BRK** (65C02): empilha PC+2 (hi, lo) e P com B=1, faz I=1, **D=0**, e salta para `[$FFFE]`; **RTI** desempilha P, lo, hi e
  **não** soma 1. A continuação `addr+2` é líder `RETADDR` (como a de um JSR).
- **BIT #imm** só altera Z (N e V ficam); `BIT` nos demais modos copia os bits 7 e 6. `LSR` zera N.
- `PHP` e `BRK` **leem** N,Z,C,V (forçam vivacidade); `PLP`/`RTI` os **redefinem**.
- **Ciclos** `[VERIFY]`: `INC/DEC abs,X` = 7 fixos; `ASL/LSR/ROL/ROR abs,X` = 6 (+1 ao cruzar página); `BRK`=7, `RTI`=6,
  `PHx`=3, `PLx`=4, RMW `zp`=5 / `zp,X`=6 / `abs`=6.
- Dois mecanismos novos no tradutor para código que não é "fixo":
  - **`param_operand` (SMC de operando imediato)**: `--smc-operand ADDR` faz o operando virar `lx_rd8(addr+1)` a cada
    execução. Erro explícito se o byte alterado for um **opcode** ou o operando de outro **modo** (ainda não suportado).
  - **Hook** (`--hook ADDR` / `analyze(hooks=)`): o endereço vira fronteira de bloco, **não é decodificado nem seguido**;
    `lx_dispatch` consulta o hook antes da tabela. Sucessor desconhecido ⇒ flags vivos (conservador).
- `LxOverlay.size` passou a `lx_u32` (uma imagem de 64 KB não cabia em `u16`).

## 3. Validação independente (Dormann) — o resultado principal desta versão

`pc-tools/tests/functional/run_dormann.sh` baixa (com **SHA-256 fixado**; as imagens **não** são redistribuídas) e executa
**pelo pipeline completo** (`lynx2c` → C89 → gcc → `lx_run`) as duas suítes de Klaus Dormann, com **sementes iterativas**:
cada PC não resolvido em execução (alvos de `RTI`, `JMP` indireto, handler de `BRK`) vira entrada e o código é retraduzido.

| Suíte | Resultado | Ciclos | Instruções traduzidas | Execução (host) |
|---|---|---:|---:|---:|
| `6502_functional_test` (NMOS documentado: todos os modos, flags, decimal, BRK/RTI, flag I) | **PASSOU** (`$3469`) | 96 709 298 | ~7,4 mil | 0,3 s |
| `65C02_extended_opcodes_test` (BRA, STZ, TSB/TRB, PHX/PHY/PLX/PLY, INC/DEC A, BIT #, `(zp)`, `JMP (abs)` sem bug de página, `JMP (abs,X)`, BRK limpa D, decimal 65C02) | **PASSOU** (`$24F1`) | 67 106 406 | ~2,5 mil | 0,2 s |

**Trechos dispensados por hook** (única diferença entre "rodou a suíte" e "rodou a suíte inteira"):

| Suíte | Trecho | Motivo |
|---|---|---|
| 6502 | `$0446→$0581` teste de faixa de desvio | reescreve o **operando de um `Bcc`** (SMC de desvio: exigiria alvo dinâmico) |
| 65C02 | `$071C`, `$0B94` | `BBR/BBS` (Rockwell) |
| 65C02 | `$0C04` | NOPs indefinidos de 1/2/3 bytes |
| 65C02 | `$1E69` | `RMB/SMB` (Rockwell) |

Cada seção dispensada exige `test_case` em sequência na seguinte, então a ordem dos testes continua verificada.

**Sensibilidade das suítes** (mutação feita à mão sobre o tradutor/runtime): `CMP` com `>`, `ROL` ignorando C, `BIT` com V do bit
errado, `BRK` sem B, `SBC` decimal com carry errado ⇒ a suíte NMOS **falha** em endereços distintos (o do SBC decimal só depois
de 84 M ciclos). `STZ` escrevendo A, `TSB` virando AND, `JMP (abs)` com o bug de wrap do NMOS, `ADC` decimal com Z "estilo NMOS"
⇒ falham **só** na suíte 65C02; a NMOS passa com eles. As duas suítes são complementares.

## 4. Verificação por testes próprios

`run_diff.sh` (≈ 45 s): **76 unitários**; diferencial de **blocos retos** com **895 632 vetores** (agora 178 opcodes; exaustivo em
`ADC/SBC/CMP #imm`) e de **programas** com **232 programas / 10 240 vetores** (trampolim real; inclui `BRK`/`RTI`, X/Y variáveis,
SMC de imediato, pilha); compilado `-std=c89 -pedantic -Wall -Wextra -Werror` em `-O0` e `-O2`.

**Dupla derivação independente da tabela de opcodes**: o `optable.json` é gerado de listas explícitas
(`lynx2c/tools/gen_optable.py`) e a referência o **deriva do padrão de bits** `aaabbbcc` + fórmulas de ciclos; os dois conjuntos
concordam nos 178 opcodes em mnemônico, modo, tamanho, ciclos e penalidade de página (`test_decode.py`).

**Teste de mutação** (≈ 45 mutantes ao todo nesta versão e nas anteriores, em cópias descartáveis), com a causa de cada detecção
atribuída (divergência real × erro de compilação). Mutantes **equivalentes** identificados: relaxar a conservadoria de `JSR` e de
`BRK` no `live_out` (ambos já forçam vivacidade por outros meios). Mutante "hook não vira líder" é pego só pelos unitários.

## 5. Limites — leia antes de confiar

- **Ciclos não são verificados por Dormann** (as suítes não os medem): continuam `[VERIFY]` contra a doc do CPU do Lynx ou um
  emulador maduro. É o item mais importante ainda sem fonte independente.
- **V em decimal** não é verificado por nenhuma das suítes (a 65C02 mascara `N-----ZC`); N, Z e C o são, para operandos BCD **válidos**.
  Operandos BCD inválidos não são verificados.
- **SMC**: só operando **imediato** (`param_operand`). Operando de desvio, de outros modos, opcode e **código gerado em RAM** não são
  suportados (exigem hook HLE por jogo). O teste de faixa de desvio do Dormann ficou dispensado por isso.
- **IRQ/NMI/WAI/STP** não são exercidos (sem agendador real; `6502_interrupt_test` exige um registrador de feedback).
- A execução é em **fase 1** (todo bloco passa pela tabela); os 0,3 s são **no host x86**, **não** uma estimativa para o ARM60.
- O oráculo próprio continua escrito por nós; o ganho desta versão é justamente ter **duas suítes de terceiros** concordando.
- Nada compilado com o armcc do SDK 3DO.

> v0.5.0 atualizou parte destes limites (opcodes/ciclos-base/BCD contra o Handy; expansão ARM medida) — ver `docs/09`.

## 6. Próximos passos sugeridos
1. **Ciclos**: obter uma fonte independente (documentação do CPU do Lynx/emulador) e transformar os `[VERIFY]` em testes.
2. **`lynxtrace` com perfil dinâmico + estágios A–C** (`ingest`, `discover`, `report.md`): o laço de sementes iterativas que já
   funciona no driver funcional é exatamente o realimentar do estágio B.
3. **Fase 2 do gerador** (registradores em locais, `JSR` como chamada C, tabela só com alvos dinâmicos) e primeira **medição de
   desempenho**, ainda no host, em comparação com o orçamento de `docs/01` §6.
4. Agendador real (`lx_sched_service`: timers/IRQ do Mikey) e `6502_interrupt_test`.
