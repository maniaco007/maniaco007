# 06 — Primeiro tradutor de opcodes: LDA, STA, ADC, SBC (v0.2.0)

Escopo: **35 opcodes** (LDA 9, STA 8, ADC 9, SBC 9), todos os modos de endereçamento
do 65C02 para esses mnemônicos: `imm, zp, zp,X, abs, abs,X, abs,Y, (zp,X), (zp),Y, (zp)`.
Blocos **retos** (sem desvios ainda): o bloco termina no fim dos bytes e retorna o PC seguinte.

## 1. O que foi construído

```
bytes 65C02 ─▶ decode ─▶ lift (IR) ─▶ opt (vivacidade de flags) ─▶ emit_c ─▶ C89
                 │                                                             │
        optable.json (dados)                                    lx_u32 f(LxCpu*) por bloco
```
| Peça | Arquivo |
|---|---|
| Tabela de opcodes (dados, D1) | `pc-tools/lynx2c/lynx2c/optable.json` + `optable.py` |
| Decoder (erro explícito p/ opcode não suportado) | `decode.py` |
| IR com `defs/uses` de flags e região do operando | `ir.py`, `lift.py` |
| Vivacidade de flags (reversa, bloco reto) | `opt.py` |
| Emissor C89 | `emit_c.py` |
| CLI | `python3 -m lynx2c {disasm,translate}` (`PYTHONPATH=pc-tools/lynx2c`) |
| Runtime necessário | `runtime/src/lx_mem.c`, `lx_alu.h` (BCD), `lx_mikey.h` (contrato) |
| Núcleo de referência (oráculo) | `pc-tools/lynxtrace/lynxtrace/core65c02.py` |

## 2. Decisões de semântica

- **Operando absoluto**: região resolvida em tempo de tradução — `<$FC00` RAM direto;
  `$FC00–FCFF` `lx_suzy_*`; `$FD00–FDFF` `lx_mikey_*`; `≥$FE00` `lx_io_*` (RAM por baixo por ora).
  **Indexado/indireto**: `lx_rd8/lx_wr8` (uma comparação). **ZP**: sempre `lx_ram`, com wrap de 8 bits,
  inclusive o ponteiro `(zp)` em `$FF/$00`.
- **Efeitos colaterais de E/S**: operando lido **uma vez**, escrito **uma vez**; leitura de `LDA` é
  feita mesmo se N/Z estiverem mortos.
- **Flags**: N/Z preguiçosos (`nsrc/zsrc`); C/V explícitos. **Flag morto não é materializado**
  (ex.: `LDA #1; LDA #2` — o primeiro não gera N/Z). Premissa conservadora: tudo vivo na saída do bloco.
- **Ciclos**: soma constante por bloco (`LX_SCHED_CHECK`); **+1 de cruzamento de página**
  (leituras `abs,X`/`abs,Y`/`(zp),Y`, não em `STA`) e **+1 em modo decimal** somados dinamicamente.
- **ADC/SBC binário**: inline. **Decimal (D=1)**: `lx_adc_dec/lx_sbc_dec`, semântica de Bruce Clark
  para 65C02 — N/Z do acumulador final; V de `ADC` pela "Seq.2"; carry/V de `SBC` iguais ao binário.
  `D` é testado em **tempo de execução** (ainda não há propagação de constantes).
- `$89` **não** é `STA #`: no 65C02 é `BIT #` (rejeitado como não suportado).

## 3. Verificação — o que os testes provam (e o que não)

`pc-tools/tests/run_diff.sh` (≈ 20 s):

1. **29 testes unitários** (`unittest`): decoder, vivacidade, propriedades do C emitido, e o próprio
   núcleo de referência contra oráculos elementares — ADC/SBC binário **exaustivo** contra aritmética
   de inteiros do Python, e ADC/SBC decimal para **todo par BCD válido** (100×100×2) contra aritmética
   decimal comum.
2. **Diferencial**: o C gerado é compilado (`-std=c89 -pedantic -Wall -Wextra -Werror`, `-O0` e `-O2`) e
   comparado ao núcleo de referência em **557 288 vetores / 1 062 funções**:
   - exaustivo `ADC #imm`/`SBC #imm`: M×A×C×D = 262 144 vetores por opcode;
   - cada um dos 35 opcodes × 10 codificações de operando (bordas de página, ZP, E/S, ROM);
   - 200 blocos aleatórios de 2–8 instruções (exercita vivacidade de flags e soma de ciclos).
   Compara A, X, Y, S, P, ciclos, PC seguinte, escritas em RAM, escritas em E/S (ordem), roteamento ao
   chip correto e escritas "estranhas" na RAM.
3. A tabela do tradutor é conferida contra uma tabela **derivada do padrão de bits** `aaabbbcc` do 6502
   (independente do JSON).

**Teste de mutação** (feito à mão, em cópia descartável): foram injetados 11 bugs realistas — limiar de
cruzamento de página, carry de entrada do SBC decimal, ADC sem "usa C" na vivacidade, Mikey↔Suzy no emissor
e no `lx_mem.c`, V do SBC, wrap de ZP,X, wrap do ponteiro ZP, ROM sem ler a RAM. **Todos** foram detectados
pelo diferencial, depois de corrigir uma lacuna que o próprio teste de mutação revelou (os stubs de Suzy e
Mikey devolviam o mesmo valor, então a troca de chip passava despercebida).

**Limites — leia antes de confiar:**
- O oráculo foi escrito por nós, da mesma fonte de semântica. Ele prova **consistência tradutor ↔ referência**,
  não fidelidade ao **hardware do Lynx**. Itens `[VERIFY]` contra o CPU real / emulador maduro: flags N/V/Z em
  decimal com operandos BCD **inválidos**, e ciclos (+1 decimal, cruzamento de página).
- Ainda não rodamos uma suíte funcional independente (ex.: testes de Klaus Dormann) nem comparamos com um
  emulador de Lynx; exigem BNE/JMP/etc. (fluxo de controle) e mais opcodes.
- Nada foi compilado com o armcc do SDK 3DO; só C89 estrito no gcc.
- Código gerado em fase 1 (registradores em `LxCpu`); sem desempenho a medir ainda.

## 4. Como reproduzir
```
pc-tools/tests/run_diff.sh                      # tudo (unitários + diferencial -O0/-O2)
SKIP_UNIT=1 pc-tools/tests/run_diff.sh          # só o diferencial
PYTHONPATH=pc-tools/lynx2c python3 -m lynx2c translate --org 0x0200 --hex "A9 01 69 02 8D 91 FC"
```

## 5. Próximos passos sugeridos
1. Ampliar o decoder/IR com o restante do grupo 1 e o fluxo de controle (`Bcc`, `BRA`, `JMP`, `JSR`, `RTS`):
   habilita CFG real, vivacidade entre blocos e a suíte funcional independente.
2. `lynxtrace` com o resto do conjunto + E/S do Lynx → perfil dinâmico (estágio B).
3. `discover` (estágios A–C) e `report.md` de elegibilidade num homebrew.
