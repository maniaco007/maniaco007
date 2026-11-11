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
Estimativas, a confirmar com o estágio E:

| Forma | ARM por instr. 65C02 | Bytes ARM por byte 65C02 (~2 B/instr) |
|---|---|---|
| ingênua (flags sempre materializados) | ~15–25 | ~30–50 |
| hot, com vivacidade de flags + regiões | ~5–9 | ~10–18 |
| cold (helpers compactos) | ~3–4 (chamadas) | ~6–8 |

Com 640 KB de código: **~35–60 KB** de 65C02 em forma *hot* (~10–18×), ou **~80–100 KB**
em *cold*. Hipótese de trabalho: jogos com **≲ 60–80 KB de código 65C02 efetivamente
alcançado** (medido pelo trace, não pelo tamanho do `.lnx`) são candidatos. O estágio
de *profiling* emite esse número **antes** de qualquer tradução (`report.md`); é o
critério objetivo de elegibilidade. Ferramentas de controle: orçamento por jogo
(`[budget] max_code_kb`), tiers hot/cold guiados por contagem, `armcc -Ospace` no cold.

Por que o orçamento aperta: o ARM60 do 3DO **não tem cache**; código grande também
custa banda de busca, não só espaço.

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
