# 05 — Riscos e decisões abertas (para aprovação)

## 1. Decisões que preciso que você aprove

Cada item tem uma **recomendação**; sem objeção, sigo as recomendações.

| ID | Decisão | Opções | Recomendação |
|---|---|---|---|
| **D1** | Linguagem do lado PC | Python 3 (só *stdlib*) · C++17 | **Python**: iteração rápida, ROMs ≤ 512 KB não exigem desempenho; tabela de opcodes em arquivo de dados → reescrita barata |
| **D2** | PC sem tradução / código gerado em RAM | só `lx_unresolved` + hook · **mini-interpretador opcional** só para regiões frias marcadas | **Sem interpretador** (respeita sua diretriz); aceitar que código **gerado em runtime** exige hook HLE por jogo. Reavaliar caso a caso |
| **D3** | Granularidade da geração | bloco-por-função + trampolim (fase 1) → rotinas com entradas (fase 2) | **Fase 1 primeiro** (corretude verificável), otimizar depois sem mudar a ABI |
| **D4** | Saída do gerador | C89 · Assembly ARM | **C89** (compila no host p/ teste diferencial); *asm* só para *hot spots* medidos |
| **D5** | Quando chamar `DrawCels` | adiado até sincronismo · imediato por `SPRGO` | **Adiado** (menos chamadas, ordem preservada) |
| **D6** | Tela | 2× inteiro (320×204 + *letterbox*) · esticar a 320×240 | **2× inteiro** (pixels uniformes; ajustável via `LX_VIEW_*`) |
| **D7** | Colisão | nenhuma · BBOX · por pixel | **BBOX por padrão**, `PIXEL` por jogo quando necessário |
| **D8** | Cartucho > ~384 KB | tudo na RAM (rejeitar) · *streaming* do CD | **Rejeitar por ora** (sua restrição); *streaming* só se aprovado |
| **D9** | Núcleo de referência (oráculo) | escrever o nosso (`lynxtrace`) · adaptar emulador existente | **Nosso, mínimo**, só o necessário p/ trace e testes; um emulador completo pode ser usado como 2º oráculo |

## 2. Riscos técnicos (ordenados por impacto)

| # | Risco | Impacto | Mitigação |
|---|---|---|---|
| R1 | **Código que não existe estaticamente** (SMC, rotinas geradas em RAM, descompressão para RAM executável) | pode inviabilizar um jogo | Detecção no trace; hook HLE por jogo; critério de elegibilidade (§3 de `04`) |
| R2 | **Orçamento de CPU** (~6 ARM/instr 65C02) | jogo lento | flags preguiçosos + vivacidade, hot/cold, medir cedo com um jogo-piloto simples |
| R3 | **Tamanho do código traduzido** (640 KB) | jogo não cabe | `report.md` com estimativa **antes** de traduzir; tiers; orçamento por jogo |
| R4 | **Colisão** (Suzy→depósito no SCB) sem equivalente no Cel Engine | jogabilidade errada | `BBOX`/`PIXEL`; escolha por jogo |
| R5 | **Fidelidade de escala/distorção** (acumuladores do Suzy vs. matriz do CCB; STRETCH, TILT+flip) | artefatos visuais | classificação `NATIVE/APPROX/FALLBACK` + diff host-vs-referência por frame |
| R6 | **Temporização** (timers, IRQ em fronteira de bloco, `busy`) | travas em *vsync-wait*, áudio fora | ciclos por bloco; verificação obrigatória em arestas de retorno |
| R7 | **Pilha emulada / RTS trick / troca de tarefas** | retorno errado | RTS verificado + `lx_dispatch`; `RETADDR` em tabela |
| R8 | **Boot cifrado e ROM de boot** | não dá p/ rodar o trace sem imagem de boot | o usuário fornece a imagem p/ o `lynxtrace`; saída não a contém; suporte a homebrew sem cifra |
| R9 | **Áudio do Mikey** (4 canais, LFSR) | sem som / fora de tempo | fora do escopo desta fase; interface reservada em `lx_mikey_*` |
| R10 | **Pouco acesso ao SDK/hardware aqui** | assinaturas/formatos do CCB errados | tudo marcado `[VERIFY]`; backend 3DO só após conferência com a doc; headers validados em C89 no host |
| R11 | **Divergências de ISA** (Lynx tem BBR/BBS/RMB/SMB? WAI/STP?) | opcodes faltando | confirmar na documentação ao escrever o decoder; teste exaustivo |

## 3. O que está explicitamente fora do escopo agora
Parser/decodificador de opcodes 65C02; geração de código dos opcodes; inicialização do
Cel Engine; HLE do Mikey/áudio; qualquer ROM ou BIOS.

## 4. Próximas etapas sugeridas (após sua aprovação)
1. Congelar decisões D1–D9 e corrigir os itens `[VERIFY]` com a documentação.
2. `lynxtrace` mínimo + `lynx2c` estágios A–C (ingest/discover) sobre um **homebrew** pequeno
   (sem cifra), gerando **apenas `report.md`** (tamanho de código, overlays, SMC).
3. Decoder + IR + emissão para **ADC, SBC, LDA, STA** (+ flags, modos de endereçamento) com a
   bateria diferencial do §9 de `02`.
4. Esqueleto do runtime no host (`lx_mem`, `lx_sched`, `lx_dispatch`) e backend de software.
5. Só então: backend 3DO e `DrawCels`.
