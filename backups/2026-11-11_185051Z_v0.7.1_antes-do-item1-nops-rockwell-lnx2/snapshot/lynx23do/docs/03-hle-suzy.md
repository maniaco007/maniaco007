# 03 — HLE do Suzy → Cel Engine

API: `runtime/include/lynx/lx_suzy.h` (+ `lx_cel.h`, `lx_platform.h`, `lx_suzy_regs.h`).
Valores de bits/registradores marcados `[VERIFY]` nos headers precisam ser conferidos
contra a documentação oficial **antes** de implementar `lx_suzy.c` (não há o SDK/doc aqui).

## 1. Princípio
O código do jogo, traduzido, continua escrevendo registradores e montando SCBs na
`lx_ram` como no original. O HLE só entra em **`SPRGO`**: percorre a cadeia de SCBs,
converte cada um em `LxCelDesc` e entrega ao backend, que no 3DO monta CCBs e chama
`DrawCels()`. O desenho "pesado" (escala, distorção, composição) vira trabalho do
Cel Engine, em paralelo com a CPU.

Camadas (todas em `runtime/`):
```
 código traduzido ─▶ lx_suzy.h  (SCB, regs, SPRGO, colisão, matemática)   [núcleo, portável]
                       │ LxCelDesc
                       ▼
                   lx_cel.h    (descritor neutro ≈ CCB; LxViewXform)        [núcleo, portável]
                       │ lx_gfx_submit_cels
                       ▼
                   lx_platform.h  backend: 3DO (CCB + DrawCels) | host (software)
```

## 2. Dado de entrada: SCB do Lynx
Cadeia ligada por `SCBNEXT` (terminada quando a parte alta é 0). Campos: `SPRCTL0`
(bpp, flips, tipo), `SPRCTL1` (literal, `RELOAD_DEPTH`, reuso de paleta, `SKIP`,
quadrante de início), `SPRCOLL`, `SCBNEXT`, `SPRDLINE`, `HPOS`, `VPOS`, e — conforme
`RELOAD_DEPTH` — `HSIZ`, `VSIZ`, `STRETCH`, `TILT`, mais 8 bytes de *pen map*.
Campos não recarregados **persistem** nos registradores (`LxSuzyRegs`); por isso
`lx_suzy_scb_decode()` combina SCB + estado.

## 3. Mapeamento SCB → CCB (formatos `[VERIFY]` contra a doc do CCB)

| Lynx (SCB/regs) | Formato Lynx | 3DO (CCB) | Fórmula (S = `LX_VIEW_SCALE`) |
|---|---|---|---|
| `HPOS/VPOS` − `HOFF/VOFF` | int16 | `XPos/YPos` 16.16 | `view(x,y)` via `LxViewXform` (2×, letterbox, rotação) |
| `HSIZ` | 8.8 | `HDX` 12.20 | `±HSIZ·2¹²·S` (sinal por `HFLIP`) |
| `VSIZ` | 8.8 | `VDY` 16.16 | `±VSIZ·2⁸·S` (sinal por `VFLIP`) |
| `TILT` | 8.8, soma em X por linha | `VDX` 16.16 | `TILT·2⁸·S` |
| `STRETCH` | 8.8, soma em `HSIZ` por linha | `HDDX` 12.20 | `STRETCH·2¹²·S·(VSIZ/256)` — **APROX** quando `VSIZ≠1,0` (o Suzy soma por linha de *destino*; o Cel Engine por linha de *fonte*) |
| `SPRDLINE` + dados | RLE 1–4 bpp, *offset* por linha | `SourcePtr` | pré-cozido → Cel *packed* 4 bpp codificado; senão conversão em runtime + cache |
| pen map (8 B) + paleta Mikey | pen→índice→RGB444 | `PLUTPtr` (16×RGB555) | `lx_suzy_resolve_plut()`; cache por (pen map, época de paleta) |
| tipo `NORMAL/NONCOLL/BOUNDARY` | pen 0 transparente | flag de transparência do Cel | `LX_BLEND_KEY0` |
| tipo `BACKGROUND/BACKGND_NOCOL/BSHADOW` | opaco | cor 0 opaca (flag BGND) | `LX_BLEND_OPAQUE` |
| tipo `SHADOW/BSHADOW` | pen `0xE` sombreia | `PIXC` (mistura 50 %/escurecer) | `LX_BLEND_SHADOW` — **APROX** |
| tipo `XOR` | XOR com fundo | *(sem equivalente)* | `LX_MAP_FALLBACK_SOFT` → rasterizador de software |
| `SKIP`, tamanho 0 | — | — | `LX_MAP_SKIP` |
| `SCBNEXT` (cadeia) | ponteiro | `NextPtr` / `LAST` | ordem preservada na fila → CCBs encadeados |

`LxMapQuality` informa `NATIVE | APPROX | FALLBACK_SOFT | SKIP`; contadores em
`LxSuzyStats` guiam, por jogo, onde o esforço de fidelidade vale a pena.

Observação-chave de memória: **o formato "packed" do 3DO é RLE por linha**, como o
do Lynx. Cozinhar para *packed* mantém o tamanho dos sprites próximo do original.
*Unpacked* só para sprites pequenos e muito usados.

## 4. Agendamento (decisão D5)
- **`LX_SCHED_DEFERRED` (recomendado):** `SPRGO` apenas **enfileira** Cels; a fila é
  descarregada em *pontos de sincronismo*: flip de buffer (`DISPADR`/vblank), leitura
  da `lx_ram` na faixa do framebuffer, troca de `VIDBASE`, polling de `SPRSYS` com fila
  longa. Poucas chamadas a `DrawCels`, ordem preservada.
- **`LX_SCHED_IMMEDIATE`:** `DrawCels` em cada `SPRGO`. Mais simples; mais chamadas.
- Em ambos: `SPRSYS.busy` é levantado e o **custo estimado do desenho do Suzy é
  debitado ao relógio do Lynx** (jogos fazem polling; a CPU real ficava parada).

## 5. Framebuffer (decisão por jogo: `LX_FB_MODE`)
O Lynx desenha no framebuffer **na RAM** (160×102, 4 bpp, **80 B/linha**), que o Mikey
exibe. Dois fatos úteis: (1) 80 B/linha = 20 palavras → **é exatamente um Cel 4 bpp
codificado *unpacked* de tela cheia** (zero-copy se alinhado a 32 bits); (2) CPU e
Suzy ambos escrevem nele.

| Modo | Comportamento | Quando |
|---|---|---|
| `LX_FB_CEL_ONLY` | sprites → Cels; escritas de CPU no fb são ignoradas | jogos que só desenham por sprites (inclusive limpar com sprite BG) |
| `LX_FB_UNDER` | fb da `lx_ram` vira Cel de fundo (`lx_gfx_submit_fb_layer`), Cels por cima | jogos que desenham fundo/texto por CPU antes dos sprites |
| `LX_FB_SOFT` | Suzy em software direto na `lx_ram`; fb inteiro vira Cel | fidelidade máxima / efeitos de leitura do fb; lento |

Superfícies: cada `VIDBASE` distinto é uma `LxSurface` (duplo buffer típico) →
`BitmapItem` na **VRAM** do 3DO (não consome os 2 MB de DRAM).

## 6. Colisão (decisão D7) — lacuna real
O Cel Engine **não** detecta colisão; o Suzy sim (grava o número de colisão no
"depósito" do SCB) e muitos jogos dependem disso. Níveis por jogo (`LX_COLL_MODE`):
`NONE` · `BBOX` (retângulos envolventes no momento do enfileiramento; padrão) ·
`PIXEL` (máscara em software, só tipos com colisão). Falsos positivos de `BBOX`
são o risco; `PIXEL` custa CPU. Escolha por jogo no manifest.

## 7. Matemática do Suzy
Multiplicação/divisão em hardware (`MATHA..MATHP`, sinal, acumulação, flags de erro
em `SPRSYS`) é **independente do Cel Engine**: implementada em C puro
(`lx_suzy_math_*`), resultado instantâneo. O ARM60 tem `MUL`, não tem divisão →
divisão por laço de subtração/shift (rara em caminho quente).

## 8. Caches e pools (sem `malloc` em laço quente)
- Pool de `LxCelDesc`/CCB: `LX_MAX_CELS_PER_FRAME` (padrão 256), duplo buffer.
- Cache de PLUT: `LX_MAX_PLUTS` (padrão 64) por (pen map, época de paleta).
- Tabela `cart_offset → Cel` (de `lxdata.idx`) + cache de runtime p/ sprites gerados em RAM.

## 9. O que **não** está resolvido (ver `05`)
Precisão de arredondamento do acumulador de escala do Suzy; `TILT` combinado com flips;
sombra/`XOR`; custo real do Cel Engine para muitos sprites escalados; temporização exata
do `busy`. Tudo medido em teste diferencial host-vs-referência antes de aceitar.
