# 04 — Orçamento de memória (2 MB de DRAM + 1 MB de VRAM)

> Todos os números abaixo são **hipóteses de partida** para dimensionar a
> arquitetura. Devem ser **medidos** (emulador de 3DO, depois hardware) antes de
> aprovar qualquer jogo. Tamanho do SO/runtime do Portfolio em particular é incerto.

## 1. Onde cada coisa mora
| Memória | Conteúdo |
|---|---|
| **VRAM (1 MB)** | superfícies de vídeo (2 × 320×240×16 bpp ≈ 300 KB) — **fora** do orçamento de DRAM |
| **DRAM (2 MB)** | SO + executável + RAM Lynx + cartucho + código traduzido + tabelas + pools |

## 2. Orçamento-alvo de DRAM (hipótese)
| Item | KB | Observação |
|---|---:|---|
| RAM do Lynx (`lx_ram`) | 64 | fixo |
| Imagem do cartucho + sprites cozidos (`lxdata.bin`) | 384 | cartuchos usuais 128–512 KB; 512 KB pede streaming (D8) |
| **Código traduzido** (hot + cold) | **640** | principal restrição — §3 |
| Tabelas de despacho / overlays / hooks | 32 | só alvos dinâmicos (§4) |
| Pools de Cels, CCBs, PLUTs, caches de sprite | 64 | |
| Runtime (HLE Suzy/Mikey, áudio, entrada, drivers) | 128 | |
| SO Portfolio, *stack*, heap, folga | 512 | **a medir** |
| **Total** | **1824** | folga ≈ 224 KB |

## 3. Expansão de código e elegibilidade de jogos

Expansão = bytes ARM gerados por byte de 65C02 de código (não de dado).

### 3.1 MEDIDO (v0.5.0) — substitui a hipótese anterior

Código traduzido pela **fase 1** do gerador (registradores em `LxCpu`), compilado com **clang -Os para ARM big-endian**
(ARM7TDMI/ARMv4, modo ARM; `lynx2c report` / `armsize.py`). Código-alvo: as duas suítes de Dormann (código real e variado):

| Suíte | Instr. 65C02 | Bytes 65C02 | ARM total | **Expansão** | ARM/instr. 65C02 |
|---|---:|---:|---:|---:|---:|
| 6502_functional_test, ABI v1 | 7 395 | 12 983 | 418 088 B | 32,2× | 13,4 |
| 6502_functional_test, **ABI v2** | 7 395 | 12 983 | 350 040 B | **27,0×** | **11,1** |
| 65C02_extended_opcodes_test, ABI v1 | 2 472 | 4 201 | 142 024 B | 33,8× | 13,6 |
| 65C02_extended_opcodes_test, **ABI v2** | 2 472 | 4 201 | 116 724 B | **27,8×** | **11,1** |

(O total inclui a tabela de despacho: 8 bytes por bloco.)

**Para onde vai o código** (`tools/opcode_cost.py`: um bloco de 1 instrução por opcode; ARM v2):
- **custo fixo por bloco: 11 instruções ARM** (era 18): prólogo/epílogo, soma de ciclos, teste de evento. Com ~2,9 instruções
  65C02 por bloco isso sozinho é ~3,8 ARM por instrução 65C02;
- custo líquido por opcode: **mediana 10, média 14, máximo 58**; `ADC`/`SBC` ~43–55 (caminho decimal + V/C/N/Z), `BRK` 58,
  modos `(zp,X)`/`(zp),Y` ~25–30;
- ganhos já obtidos na fase 1 (v0.5.0): `LX_SCHED_CHECK` com chamada final (sem quadro de pilha no caminho comum) e
  ajudantes decimais fora de linha — **−16% de código**, nada regrediu (diferencial + Dormann).

**Consequência para o orçamento de 640 KB de código:** na expansão medida cabem **~23–24 KB de código 65C02 alcançado**
(antes: "~60–80 KB"). A hipótese de 10–18× para a forma *hot* **não** vale na fase 1.

**Ressalvas:** (1) o clang -Os costuma gerar código **menor** que o armcc 2.x do SDK 3DO: tratar como **piso**;
(2) o código do Dormann testa flags após quase toda operação (flags vivos) — mas ainda assim **69 %** das definições de flag
foram eliminadas; jogos reais tendem a ser mais favoráveis; (3) é tamanho estático, não desempenho (ver §3.3).

### 3.1b MEDIDO (v0.6.0) — fase 2 (rotinas fundidas, registradores locais, limite de 32 blocos/rotina)

| Suíte | Fase 1 (ABI v2) | **Fase 2** | ARM/instr. 65C02 |
|---|---:|---:|---:|
| 6502_functional_test | 27,0× | **17,9×** (232 032 B) | **7,1** |
| 65C02_extended_opcodes_test | 27,8× | **18,5×** (77 760 B) | **7,1** |

Na expansão da fase 2 cabem **~35–36 KB de código 65C02 alcançado em 640 KB** (fase 1: ~23 KB). Achado central: **a fusão sem limite quase não
ajuda (25,4×) e gera quadro de pilha de 15 KB**, porque ~16 variáveis vivas não cabem nos ~12 registradores do ARM (27% das instruções viram
spill/reload). Limitar a rotina a 32 blocos dá 17,7× e quadro de 44 B. Detalhes e a varredura completa: `docs/10`.

### 3.2 O que ainda falta atacar (ordenado por ganho esperado; itens 1–2 da lista original já feitos na fase 2)
1. ~~Registradores e flags em variáveis locais~~ — **feito** (fase 2);
2. ~~Fundir blocos~~ — **feito em parte**: fall-through/desvios fundidos; falta **`JSR` como chamada C nativa** (fase 2b);
3. Caminho decimal fora do caminho comum (já fora de linha) e `V`/`C` só quando vivos (já feito);
4. Forma *cold* compacta (chamadas a ajudantes por opcode) para blocos de baixa contagem no perfil dinâmico.
**Meta de projeto: ≤ ~10× e ≤ ~6 ARM por instrução 65C02** (docs/01 §6) — o que daria ~64 KB de 65C02 em 640 KB. **Situação (v0.6.0): 17,9× e 7,1.**

### 3.3 Elegibilidade (critério objetivo)
`lynx2c report` mede o **código 65C02 alcançável** e o tamanho **ARM real** do jogo, e dá o veredito de tamanho contra
`[budget] max_code_kb`. Hoje (fase 2) cabem jogos com **≲ 35 KB de código alcançado** em 640 KB (fase 1: ≲ 23 KB); a fase 2b e a forma
*cold* são o caminho para ~64 KB. Ferramentas de controle: orçamento por jogo, tiers hot/cold guiados pelo perfil dinâmico, `armcc -Ospace` no cold.

Por que o orçamento aperta: o ARM60 do 3DO **não tem cache**; código grande também custa banda de busca, não só espaço.

## 4. Tabelas de despacho
8 bytes/entrada (`LxDispatchEntry`). Só entram alvos de `JMP` indireto, continuações
de `JSR` sujeitas a *RTS trick*, vetores e hooks — tipicamente centenas a poucos
milhares ⇒ ≲ 32 KB. Desvios/chamadas estáticos não ocupam tabela.

## 5. Overlays
A RAM Lynx (64 KB) é única; overlays trocam o **conteúdo** dela, não a DRAM do 3DO. O
código traduzido de **todos** os overlays reside na DRAM ao mesmo tempo (por isso o teto
de 640 KB soma todos). Só `lx_ram` e os dados lidos do cartucho mudam em execução.

## 6. Alternativas se estourar (não implementar sem aprovação)
1. *Cold tier* mais agressivo / compressão de código frio e descompressão por overlay.
2. **Streaming do cartucho pelo CD** (D8): o 3DO lê 2× do disco; sprites/dados não
   residentes. Contraria a restrição "ROM inteira em RAM"; só como escape.
3. Rejeitar o jogo (critério objetivo do §3).
