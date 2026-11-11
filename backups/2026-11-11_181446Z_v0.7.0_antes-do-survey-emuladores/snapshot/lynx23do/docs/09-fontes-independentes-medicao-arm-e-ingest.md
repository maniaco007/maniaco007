# 09 — Fontes independentes (Handy), medição ARM real e estágio A (v0.5.0)

Três frentes: (1) tirar `[VERIFY]` do conjunto de opcodes, ciclos e BCD usando um **emulador de Lynx maduro como segunda fonte**;
(2) **medir** a expansão de código ARM, que era hipótese; (3) estágio A do pipeline (`ingest`) e o `report.md` de elegibilidade.

## 1. Comparação com o Handy (dado de referência, nenhum código copiado)

`tools/extract_handy_ref.py` extrai de `c65c02.h` (libretro-handy) uma tabela de **fatos** por opcode — operação, ciclos
(`1 + N×CYC` → ciclos do datasheet `N+1`) e se é ilegal — gravada em `lynx2c/data/handy_reference.json`.
`test_handy_reference.py` fixa o resultado.

**O que isso resolve**

| Pergunta | Resposta (Handy) |
|---|---|
| O CPU do Lynx tem `BBR/BBS/RMB/SMB` (Rockwell)? | **Não**: todos ilegais no Handy |
| NOPs indefinidos de 2/3 bytes? | **Ilegais** no Handy (os 76 opcodes que eu rejeito são exatamente os ilegais dele) |
| Opcodes do Handy que faltam na minha tabela | só **`WAI` (`$CB`) e `STP` (`$DB`)** — dependem do agendador (dormir até IRQ / parar) |
| Mnemônicos | **178/178 coincidem** |
| Ciclos-base | **172/178 coincidem**; 6 divergências, todas explicadas abaixo |

**Divergências de ciclo-base (fixadas em teste)**

| Opcode | Nosso | Handy | Leitura |
|---|---:|---:|---|
| `ORA #imm` ($09) | 2 | 3 | anomalia do Handy: os outros 8 imediatos (AND/EOR/ADC/SBC/CMP/LDx…) dão 2 |
| `ASL/ROL/LSR/ROR abs,X` ($1E $3E $5E $7E) | 6 (+1 ao cruzar página) | 7 fixo | **aberto** `[VERIFY]`: 65C02 (nosso) × estilo NMOS (Handy) |
| `BRA` ($80) | 2 + 1 (tomado) | 3 | só representação: a soma é 3 nos dois |

**O que o Handy NÃO valida** (ele não modela): penalidade de cruzamento de página, +1 do desvio tomado, +1 do modo decimal.
Esses três extras continuam **sem fonte independente**.

### BCD decimal: segunda implementação independente
`test_handy_decimal.py` transcreve o ramo decimal de `xADC`/`xSBC` do Handy e o compara **exaustivamente**
(A × M × C = 131 072 casos por operação) com a minha referência. Resultado: **0 divergências nos 5 campos (A, C, V, N, Z)**,
**inclusive com operandos BCD inválidos e o flag V** — justamente o que as suítes de Dormann não verificam (mascaram `N-----ZC`
e usam só BCD válido). Sensibilidade do teste conferida: uma perturbação real do `ADC` gera 34 728 divergências e a do `SBC` 488;
a perturbação do limiar `> $99` é **equivalente** (o nibble alto é múltiplo de `$10`) e por isso não difere.
Ressalva: são duas implementações independentes **entre si** (Clark × Handy), não o silício do Lynx.

## 2. Expansão de código ARM: **medida**

`armsize.py` compila o C gerado com **clang → ARM big-endian** (ARM7TDMI, modo ARM) e lê os tamanhos com `llvm-size`.
Resultado completo e consequências para o orçamento: **`docs/04` §3**. Em resumo (fase 1, `-Os`):

- **27× em bytes, 11,1 instruções ARM por instrução 65C02** (a hipótese anterior era 10–18× e ~5–9) — os dois lotes de Dormann
  concordam (27,0× e 27,8×);
- `tools/opcode_cost.py`: **custo fixo de 11 ARM por bloco**, mediana de 10 e média de 14 por opcode, `ADC`/`SBC` ~43–55;
- duas correções baratas já aplicadas (**ABI v2**): `LX_SCHED_CHECK` com chamada final e ajudantes decimais fora de linha:
  **−16% de código**, com diferencial e Dormann inalterados;
- **na expansão medida cabem ~23–24 KB de código 65C02 alcançado em 640 KB**: a **fase 2 do gerador passa a ser pré-requisito**
  para a maioria dos jogos, não otimização opcional.

## 3. Estágio A (`ingest`) e `report.md`

`ingest.py` (formatos confirmados contra o Handy, como dado):

- **`.lnx`**: `LYNX` + `page_size` bank0/bank1 (**little-endian**, banco = `page_size × 256` bytes: `$100`→64 KB … `$800`→512 KB) +
  `version==1` + nome[32] + fabricante[16] + rotação (0/1/2) + AUDIN + EEPROM. **Jogos comerciais não têm código conhecido sem
  executar a ROM de boot** (1º bloco cifrado): o `report` diz isso em vez de inventar.
- **BS93** (homebrew): 10 bytes `80 08` + `load_address` **big-endian** + `size` **big-endian** + `BS93`. O cabeçalho é executável
  (`BRA +8`); o arquivo vai para `load_address−10` e o PC inicial é o próprio cabeçalho — encaixa direto no CFG (testado).
- **raw**: imagem plana com `--org`.

`lynx2c report` (BS93 ou imagem plana) gera o `report.md`: código alcançável (blocos, instruções, bytes), saídas dinâmicas,
sucessores fora do código conhecido, flags eliminados, acessos por região, **tamanho ARM medido**, veredito contra o orçamento e
uma seção "o que este relatório NÃO diz". Sem clang, usa o fator de referência e **rotula como estimativa**.
`run_functional.py --report` produz o relatório das suítes Dormann.

## 4. Verificação desta versão

**101 testes unitários** (novos: ingest 12, relatório 4, Handy 6, decimal Handy 3); diferencial de blocos (895 632 vetores) e de
programas (10 240) em `-O0`/`-O2`; Dormann 6502 e 65C02 **continuam passando com o ABI v2**.
Mutação nos pontos novos: o ABI bump foi **pego pelo próprio guarda de compilação** do código gerado (um teste com `abi` fixo recusou
compilar); `sched` devolvendo `pc+1` → diferencial e Dormann; `sched` sem somar ciclos → **não-terminação** (agora detectada pelo
**vigia** `HARNESS_TIMEOUT` do `run_diff.sh`); `ADC decimal sem +$60` e `SBC decimal com carry errado` → Dormann (`$3477`, `$3489`).

## 5. Limites

- Ciclos: base validada contra o Handy (172/178); **extras dinâmicos e os 4 shifts `abs,X` seguem sem fonte independente**.
- A medição é **estática**, de **clang -Os** (piso: o armcc tende a gerar mais), em **fase 1**; não é desempenho.
- `report` só vê o código **alcançável** pelas entradas dadas (subestima se há alvos dinâmicos não vistos).
- **`lynxtrace` com perfil dinâmico continua por fazer** (exige modelo de hardware e a ROM de boot do usuário); `WAI/STP` esperam o agendador.
- Nenhuma ROM comercial foi usada (não há acesso a elas): `ingest`/`report` foram testados com `.lnx`/BS93 **sintéticos** e com as suítes.

## 6. Próximos passos sugeridos
1. **Fase 2 do gerador** (registradores em locais, `JSR` como chamada, fusão de blocos): alvo ≤ 10× e ≤ 6 ARM/instr. Medir de novo com
   `report`/`opcode_cost.py` e manter Dormann + diferencial como rede de segurança.
2. Agendador real (`lx_sched_service`: timers/IRQ do Mikey), `WAI/STP` e `6502_interrupt_test`.
3. `lynxtrace` com perfil dinâmico (estágio B) para jogos com a ROM de boot fornecida pelo usuário.
