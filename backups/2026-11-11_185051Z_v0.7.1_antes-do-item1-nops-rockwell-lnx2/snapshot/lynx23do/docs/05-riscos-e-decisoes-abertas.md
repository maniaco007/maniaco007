# 05 — Riscos e decisões abertas (para aprovação)

## 1. Decisões D1–D9

**Status: aprovadas ("pode seguir") com as recomendações abaixo.** D1 (Python), D2 (sem interpretador),
D3 (fase 1: bloco-por-função), D4 (C89) já estão em uso no tradutor v0.2.0; D5–D9 valem para as fases do
HLE/memória ainda não implementadas.

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
| R2 | **Orçamento de CPU** (~6 ARM/instr 65C02) | jogo lento | **medido (estático): 11,1 ARM/instr na fase 1 → 7,1 na fase 2** (docs/10) — perto da meta (~6); fase 2b (`JSR` nativo) falta; desempenho dinâmico ainda não medido |
| R3 | **Tamanho do código traduzido** (640 KB) | jogo não cabe | **MEDIDO: 27× (fase 1) → 17,9× (fase 2) ⇒ ~35 KB de 65C02 em 640 KB** (docs/04 §3, docs/10). `lynx2c report` mede o jogo real; meta ≤10× exige fase 2b + forma *cold* |
| R4 | **Colisão** (Suzy→depósito no SCB) sem equivalente no Cel Engine | jogabilidade errada | `BBOX`/`PIXEL`; escolha por jogo |
| R5 | **Fidelidade de escala/distorção** (acumuladores do Suzy vs. matriz do CCB; STRETCH, TILT+flip) | artefatos visuais | classificação `NATIVE/APPROX/FALLBACK` + diff host-vs-referência por frame |
| R6 | **Temporização** (timers, IRQ em fronteira de bloco, `busy`) | travas em *vsync-wait*, áudio fora | ciclos por bloco; verificação obrigatória em arestas de retorno. **Refinado (docs/12 §3–4):** unidade real = ticks de 16 MHz (busca 4, dado 5; `MAPCTL.7`), quadro dirigido pelos timers 0/2 (50–75 Hz conforme o jogo) — a constante `66 667` do M1 é provisória |
| R7 | **Pilha emulada / RTS trick / troca de tarefas** | retorno errado | RTS verificado + `lx_dispatch`; `RETADDR` em tabela |
| R8 | **Boot cifrado e ROM de boot** | não dá p/ rodar o trace sem imagem de boot | o usuário fornece a imagem p/ o `lynxtrace`; saída não a contém; suporte a homebrew sem cifra |
| R9 | **Áudio do Mikey** (4 canais, LFSR) | sem som / fora de tempo | fora do escopo desta fase; interface reservada em `lx_mikey_*` |
| R10 | **Pouco acesso ao SDK/hardware aqui** | assinaturas/formatos do CCB errados | **reduzido (v0.7.0):** CCB, flags, ponto fixo e funções conferidos nos headers reais do SDK e no nes-3do; backend analisado contra os headers com sensibilidade provada. **Ainda aberto:** nada foi compilado com o armcc nem executado (docs/11 §5–6) |
| R11 | **Divergências de ISA** (Lynx tem BBR/BBS/RMB/SMB? WAI/STP?) | opcodes faltando | **REVISTO (docs/12 §2, 3 emuladores):** Lynx I sem Rockwell (NOPs de 1 B); **Lynx II tem** RMB/SMB/BBR/BBS (5 ciclos); `CB`/`DB` são **NOP de 1 B** (só o Handy os faz dormir); o Lynx I tem 14 NOPs multi-byte que o `lynx2c` hoje recusa. Tabela de ciclos/tamanhos dos 178 opcodes **confere 100 %** com o Gearlynx |

| R12 | **Taxa de quadros ≠ 60 Hz** (jogos a 50/52/75 Hz; 3DO apresenta a 60) | jogo lento/rápido ou *tearing* | lógica por ticks, apresentação desacoplada com repetição/descarte de quadros (docs/12 §4.1) |
| R13 | **Licença de código de terceiros** (Gearlynx é GPLv3; Handy zlib-like; Felix/Cardputer MIT) | contaminação do framework | só **fatos** de hardware dos GPL, sempre com 2ª fonte; código só de MIT com crédito em `NOTICE` (docs/12) |
| R14 | **Discordância entre emuladores** (page-cross em leitura indexada; fronteira de 16 B do modo página; `WAI/STP`) | erro de ±1 ciclo ou opcode errado | decisão registrada em docs/12; árbitro = captura de hardware (`tests/logic-analyzer` do Gearlynx) / ROMs de teste |

## 3. O que está explicitamente fora do escopo agora
Parser/decodificador de opcodes 65C02; geração de código dos opcodes; inicialização do
Cel Engine; HLE do Mikey/áudio; qualquer ROM ou BIOS.

## 4. Próximas etapas

> v0.2.0 concluiu parte do item 3 (ADC, SBC, LDA, STA) — ver `docs/06`. v0.3.0 trouxe o fluxo de controle, CFG e
> `lx_run` — ver `docs/07`. v0.4.0 completou o conjunto de opcodes e validou com Dormann — ver `docs/08`, que lista os próximos passos.

1. Congelar decisões D1–D9 e corrigir os itens `[VERIFY]` com a documentação.
2. `lynxtrace` mínimo + `lynx2c` estágios A–C (ingest/discover) sobre um **homebrew** pequeno
   (sem cifra), gerando **apenas `report.md`** (tamanho de código, overlays, SMC).
3. Decoder + IR + emissão para **ADC, SBC, LDA, STA** (+ flags, modos de endereçamento) com a
   bateria diferencial do §9 de `02`.
4. Esqueleto do runtime no host (`lx_mem`, `lx_sched`, `lx_dispatch`) e backend de software.
5. Só então: backend 3DO e `DrawCels`.
