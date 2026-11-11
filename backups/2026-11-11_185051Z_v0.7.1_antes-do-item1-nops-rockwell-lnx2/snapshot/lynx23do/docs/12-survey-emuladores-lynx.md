# 12 — Survey de quatro emuladores de Lynx: o que aprendemos e o que muda

Leitura **somente-leitura** (clones rasos em `/home/user/<dono>/<repo>`, nada executado) de:

| Repo | Commit lido | Licença | Natureza |
|---|---|---|---|
| `laoo/Felix` | `f5a9cda` (2025-04-29) | MIT | C++20, **precisão por acesso de barramento** (CPU e Suzy como corrotinas), fila de eventos em ticks de 16 MHz, HLE da ROM de boot |
| `drhelius/Gearlynx` | `94068da` (2026-11-04) | **GPLv3** | C++, precisão por instrução + **barramento/roubo de ciclos do Suzy**, Lynx I/II, depurador, testes com captura de analisador lógico de hardware real |
| `libretro/libretro-handy` | `bc55d46` (2026-04-20) | zlib-like (K. Wilkins) | Handy (a referência histórica) + camada libretro |
| `geo-tp/Cardputer-Game-Station-Emulators` | `74b4776` (2026-05-25) | MIT | 16 núcleos (NES, SMS, Lynx…) em ESP32-S3 com < 256 KB de RAM; **o Lynx é o Handy** (cópia podada) |

> **Regra de licença (importante):** do Gearlynx (GPLv3) e do Handy só usamos **fatos de hardware** (números, tabelas de
> comportamento) e sempre conferidos por uma segunda fonte; **nenhum código foi copiado**. A ferramenta
> `pc-tools/lynx2c/tools/crosscheck_gearlynx.py` lê uma tabela local do Gearlynx e **não a redistribui**. Se um dia
> quisermos reutilizar código, só do Felix (MIT) ou do Cardputer (MIT), com crédito em `NOTICE`.

## 1. Veredicto em uma tabela

| Pergunta que estava aberta | Resposta (fonte) | Efeito no projeto |
|---|---|---|
| Ciclos-base e tamanhos dos 178 opcodes estão certos? | **Sim, 0 divergências** contra as tabelas Lynx I e II do Gearlynx (rodado: `crosscheck_gearlynx.py`). Terceira fonte independente, além do Handy e do Dormann | `[VERIFY]` de ciclos-base **fechado** |
| ADC/SBC decimal custa +1 ciclo? | Sim — Gearlynx (`m_s.cycles++`) e Felix (leitura extra `if (state.d)`) concordam; o Handy **não** modela | nosso modelo (+1) está certo |
| Desvio tomado +1, +1 se cruza página? | Sim — Felix (leituras extras) e Gearlynx (`OPcodes_Branch`) concordam | nosso modelo está certo |
| Leitura `abs,X`/`abs,Y`/`(zp),Y` com cruzamento de página: +1? | **Felix: sim** (leitura "fantasma" quando `eah != fah`); **Gearlynx e Handy: não** (tabela fixa) | **discordância entre fontes**; mantemos +1 (modelo do Felix, o único por acesso real). Impacto baixo; ver §3.3 |
| O Lynx tem `RMB/SMB/BBR/BBS`? | **Lynx II sim, Lynx I não** (tabelas do Gearlynx e microcódigo do Felix). Corrige a premissa "Lynx não tem Rockwell" (R11) | R11 corrigido; ver §2 |
| `WAI` (`CB`) e `STP` (`DB`) existem no Lynx? | **Provavelmente não**: Felix (`UND_1_cb/db`) e Gearlynx (`UnofficialOPCode`) os tratam como **NOP de 1 byte/1 ciclo**; só o Handy os implementa (como "dormir até o IRQ"). **Corrige** o que registrei em R11 (baseado só no Handy) | tratar como NOP 1 B/1 c; o mecanismo real de dormir é `CPUSLEEP` (`$FD91`) do Mikey |
| O 65C02 do Lynx I tem NOPs de vários bytes? | **Sim**: `02,22,42,62,82,C2,E2` (2 B/2 c), `44` (2 B/3 c), `54,D4,F4` (2 B/4 c), `5C` (3 B/8 c), `DC,FC` (3 B/4 c) | hoje o `lynx2c` **recusa** esses opcodes; ver §2 |
| O custo real de um ciclo de CPU é uniforme? | **Não.** Busca de instrução = **4 ticks** (modo página da DRAM), demais acessos = **5 ticks** (clock mestre 16 MHz). `MAPCTL` bit 7 desliga o modo sequencial | o `LX_CYCLES_PER_FRAME = 66 667` (4 MHz) é uma aproximação; ver §3 |
| A taxa de quadros é 60 Hz? | **Varia por jogo** (50/52/60/75 Hz nas capturas do Gearlynx); é definida pelos timers 0 e 2 | o agendador deve ser **dirigido pelos timers**, não por constante; ver §4 |
| Como o Suzy acumula tamanho/estiramento/inclinação? | Algoritmo completo no Felix (`SuzyProcess.hpp`) | confirma e detalha `docs/03`; fornece a especificação de um **oráculo de sprites**; ver §5 |
| Precisamos da imagem da ROM de boot e de cifra? | **Não para executar**: o Felix substitui a ROM por 3 armadilhas (HLE) e só precisa **decifrar o 1º bloco**; estado de saída conhecido | R8 reduzido; ver §6 |

## 2. CPU: o conjunto de instruções real

* **Lynx I** (todos os cartuchos comerciais): 65C02 *sem* `RMB/SMB/BBR/BBS` (os 32 códigos `x7`/`xF` são **NOPs de 1 byte, 1 ciclo**)
  e com 14 NOPs de vários bytes (tabela acima). `CB` e `DB` (`WAI`/`STP` no 65C02 padrão) são **NOPs de 1 byte, 1 ciclo** segundo Felix e
  Gearlynx (o Handy os implementa como "dormir", **discordando** dos dois emuladores mais precisos; seguimos os dois).
* **Lynx II** (revisão posterior; sinalizada no cabeçalho `LNX2`, bit 0 de `flags`): acrescenta os 32 opcodes Rockwell,
  **5 ciclos** (`RMB/SMB zp`: 2 B; `BBR/BBS zp,rel`: 3 B, mais o custo de desvio tomado). Os mesmos NOPs multi-byte continuam.
* **Consequência para o `lynx2c`** (tarefa nova, barata, **ainda não feita**): (a) decodificar os 14 NOPs multi-byte como NOP com
  tamanho/ciclos da tabela — sem isso, um jogo que os use faz o CFG **falhar com erro explícito** (comportamento atual, seguro);
  (b) `RMB/SMB/BBR/BBS` só se o `.lnx`/LNX2 declarar Lynx II (flag `--lynx2`), senão tratar como NOP de 1 byte (é o que o
  hardware Lynx I faz — um código que depende disso seria bug do jogo, mas **é** o comportamento real).
* A ferramenta de cruzamento imprime a lista exata de opcodes que o hardware executa e nós não decodificamos.

## 3. Modelo de tempo: ticks de 16 MHz

### 3.1 O que os três modelos fazem
| | Unidade | Custo de um acesso | Estado |
|---|---|---|---|
| **Handy** | instrução = `1 + 5·(ciclos−1)` ticks (`CPU_RDWR_CYC = 5`) | uniforme (5), **sem** modo página | simples; **subestima** 1–2 ticks por instrução vs. Felix |
| **Gearlynx** | `cycles·5 − desconto` | 5 ticks, **−1** por byte de código sequencial dentro da mesma linha de 16 bytes (`(addr & 0xF) != 0`), só com `MAPCTL.7 = 0` | por instrução, + roubo de ciclos do Suzy/cartucho |
| **Felix** | ticks absolutos de 16 MHz | busca (opcode/operando) = `mFastCycleTick` (4; **5** se `MAPCTL` desliga o modo sequencial); leitura/escrita = 5; Suzy/Mikey têm espera própria | por **acesso**; fila de eventos |

Os dois modelos precisos **concordam** num ponto: dentro de uma instrução em linha reta,
`ticks = 4·(bytes da instrução) + 5·(ciclos − bytes)`. Conferi que isso é idêntico a `5·ciclos − bytes` do Gearlynx quando todos os
bytes de código são "sequenciais". As diferenças restantes são pequenas: o Gearlynx também desconta/quebra o modo página em
fronteiras de 16 bytes e depois de acessos a dados; o Felix (0.6.4: *"more accurate opcode/operand fetch timing"*) ignora a fronteira.

Exemplos (ticks, modelo Felix/Gearlynx → Handy): `LDA #imm` 8 → 6; `LDA abs` 17 (3 buscas·4 + 1 leitura·5) → 16; `STA zp` 13 → 11;
`JSR` 27 → 26. O Handy fica 1–2 ticks abaixo por instrução (até ~25 % em instruções de 2 ciclos) — nossa escala de
`66 667 ciclos` ≈ 4 MHz é, por sua vez, **otimista** (assume 4 ticks por ciclo inclusive nos acessos a dados).

### 3.2 Custos de barramento além da CPU (valores do Gearlynx; ordem de grandeza confirmada no Felix)
* Leitura de registrador do Suzy: **+3** ciclos de barramento; escrita no Suzy/Mikey: 0; leitura de cartucho: **+7**.
* Acesso a registradores de **timer/áudio do Mikey** sincroniza com a grade de 16 ticks do timer (Felix: `Mikey::requestAccess`).
* DMA de vídeo do Mikey rouba o barramento a cada linha (Felix: `6·fast + 2·5` ticks por rajada; Gearlynx: rajada LCD de 28 ticks).
* Suzy desenhando rouba RAM da CPU (Gearlynx: `ApplyBusStall`, ciclos "roubados"); a CPU só para quando precisa do barramento.

### 3.3 Decisão proposta (M2) — **não implementada ainda**
1. O tradutor passa a emitir, por bloco, **ticks** (não ciclos): `ticks_estático = Σ(4·bytes + 5·(ciclos−bytes))`, com os mesmos
   termos dinâmicos de hoje (+decimal, +desvio tomado, +cruzamento). Custo: mudança de constante na tabela + um fator no
   agendador; os testes diferenciais passam a comparar ticks (o oráculo `lynxtrace` ganha o mesmo modelo — fonte independente: Felix).
2. `LX_CYCLES_PER_FRAME` deixa de existir; o quadro termina quando o **timer 2** (vblank) dá *borrow* (ver §4).
3. Penalidade de cruzamento de página em leituras indexadas: mantemos +1 (Felix, por acesso). Se um jogo real divergir do hardware,
   a captura de analisador lógico do Gearlynx (`tests/logic-analyzer/*.dsl`) é o árbitro.
4. `MAPCTL.7` (sequencial desligado) muda busca de 4→5 ticks; vira um bit no estado do agendador.

## 4. Mikey: timers, quadro e interrupções (para M2)

Topologia (Felix `Mikey.cpp`, conferida com as constantes de endereço do Gearlynx), 12 contadores de 8 bits:

```
timer 0 (linha/HBLANK) ──borrow──▶ timer 2 (contador de linhas/VBLANK) ──▶ timer 4
timer 1 ──▶ timer 3 ──▶ timer 5 ──▶ timer 7 ──▶ áudio 0 ──▶ áudio 1 ──▶ áudio 2 ──▶ áudio 3 ──▶ timer 1 (laço de encadeamento)
timer 4 = UART (ComLynx)          timer 6 = independente
IRQ: timer N levanta a máscara (1<<N) em INTSET para N = 0..7; os timers de áudio (8..11) NÃO geram IRQ
```
* Período de um timer: `(1 + valor) · 2^prescale · 16` **ticks** (prescale 0 = 1 µs). Reload conforme `ENABLE_RELOAD`; `LINKING`
  faz o timer contar por *borrow* do anterior em vez de por relógio.
* **Quadro**: timer 0 define a linha, timer 2 conta as linhas. Valores típicos (derivados: 159 µs × 105 linhas ≈ 16,7 ms → 59,9 Hz;
  conferir na ROM de cada jogo): `TIM0BKUP = 0x9E`, `TIM2BKUP = 0x68`. Outros jogos usam 75/52/50 Hz (capturas de hardware do Gearlynx).
* **Pontos finos que o Felix expõe e que um HLE ingênuo erra**: `DISPADR` é travado **uma vez por quadro**, quando o contador do
  timer 2 chega a **101** (escrever `DISPADR` no meio do quadro vale só para o próximo); `CONTROLB` tem *borrow-in/out* e *last-clock*
  com janela de 16 ticks; ler `COUNT` recalcula o valor a partir do instante (os timers são **preguiçosos**: só agendam o próximo
  disparo, não contam a cada ciclo).
* **IRQ** é por nível: `INTSET`/`INTRST` (`$FD81`/`$FD80`), a CPU vê IRQ se `I = 0`; `CPUSLEEP` (`$FD91`) é o `WAI` do sistema
  (a CPU dorme até o IRQ). Gearlynx modela o sono em fatias de 8 ticks.
* **Áudio**: 4 canais de LFSR, cada um acionado pelo seu timer (8–11); amostragem a `16 000 000 / SPS`; o Gearlynx aplica passa-baixa
  de polo único (`y += α(x−y)`, corte ≈ 1 kHz) para imitar o hardware; Lynx II tem estéreo/atenuação (`ATTENREG`, `MPAN`, `MSTEREO`).
  **Para nós**: HLE de áudio = executar a máquina de estados dos 4 canais por amostra numa thread/ISR do 3DO (SDK `audio folio`
  ou DSP via *sound spooler*); a decisão fica para depois do M3.
* **UART/ComLynx** e **EEPROM** (93C46…93C86, bit-bang via `IODAT`/`AUDIN`, 8 ou 16 bits, arquivo `.e2p`): fora do escopo atual;
  EEPROM é necessária para salvar recordes em vários jogos (3DO: `OpenDiskStream`/NVRAM — a definir).

**Plano M2 resultante**: (1) `lx_mikey` com 8 timers + cadeia + IRQ por nível; (2) agendador por *próximo evento* em ticks (como o Felix),
não por quadro fixo; (3) vblank real = *borrow* do timer 2, o que destrava jogos que esperam o IRQ; (4) `CPUSLEEP` (`CB`/`DB` são NOP);
(5) teste `6502_interrupt_test` e comparação com o oráculo.

### 4.1 Taxa de quadros ≠ 60 Hz no 3DO
O 3DO apresenta a 60 Hz (NTSC). Um jogo de 75 Hz **roda a lógica a 75 Hz** (dirigida por timers); a apresentação deve **pular** 1 em
cada 5 quadros do Lynx (ou 50 Hz: repetir). Ou seja: **lógica e apresentação desacopladas** — rodar a máquina por ticks e apresentar o
último quadro completo a cada VBL do 3DO. O Cardputer faz o mesmo na prática (renderiza ao menos 1 de cada 3 quadros).

## 5. Suzy: especificação precisa para o HLE e para um oráculo de sprites (M3)

O laço de sprite do Felix (`SuzyProcess.hpp`, ~480 linhas, escrito a partir do hardware e do Handy) é a melhor especificação que
encontrei. Resumo do que **confirma ou acrescenta** a `docs/03`:

1. **SCB** é lido byte a byte: `SPRCTL0, SPRCTL1, SPRCOLL, SCBNEXT(2)`; se o bit *skip* está ligado, para aí (e o SCB seguinte é lido).
   Depois `SPRDLINE, HPOS, VPOS` (2 B cada) e, conforme `RELOAD_DEPTH`: **HVST** (`HSIZ,VSIZ,STRETCH,TILT`), **HVS**, **HV** ou nada;
   `TILT`/`STRETCH` **zeram** quando não recarregados. Depois o *pen map* (2 × 4 B, 16 nibbles) **a menos que** "reusar paleta".
2. **Quadrantes**: 4 passadas na ordem dada por `SPRCTL1` (quadrante inicial); cada uma com sinais `left/up` **xor** os flips H/V.
   **Correção de 1 pixel**: quadrantes que desenham em sentido oposto ao do quadrante 0 começam deslocados de 1 pixel (herdado do Handy,
   "evita aparência achatada" em sprites de vários quadrantes). Isso afeta o mapeamento SCB→CCB: **ignorar causa 1 px de erro**.
3. **Acumuladores** (confirmam a linha `STRETCH` APROX de `docs/03`): `vsizacum += SPRVSIZ` **por linha de fonte** → `pixelHeight = vsizacum.h`
   linhas de destino; `hsizacum += SPRHSIZ` **por pixel de fonte** → `pixelWidth = hsizacum >> 8` colunas. Por linha de destino:
   `SPRHSIZ += STRETCH` e `tiltacum += TILT`; `HPOSSTRT += (int8)tiltacum.h` antes de cada linha. Com `VSTRETCH` (SPRSYS): `SPRVSIZ += STRETCH·pixelHeight` **por linha de fonte**.
   Valores iniciais: `hsizacum = left ? 0 : HSIZOFF`, `vsizacum = up ? 0 : VSIZOFF`. O Cel Engine só tem `HDDX/HDDY` constantes por Cel — daí `APROX`.
4. **Fim do sprite**: `SPRDLINE offset == 0` encerra **todos** os quadrantes; `offset < 2` encerra o quadrante; linha fora da tela
   (`vpos ≥ 102` indo para baixo, `< 0` indo para cima) interrompe a passada. `SCBNEXT` com byte alto 0 encerra a lista; `SPRSTOP` interrompe.
5. **Colisão**: desligada por `SPRSYS.dontcollide`, bit `NO_COLLIDE` do SPRCOLL ou tipos `NONCOLL`/`BACKNONCOLL`. O depósito (`FRED`, em
   `SCBADR + COLLOFF`) recebe o **maior número de colisão** encontrado (`& 0x0F`); com `EVERON` e algum pixel desenhado, o bit `0x80`.
   É o que o `BBOX`/`PIXEL` de `docs/03` §6 precisa reproduzir — agora com a regra exata do depósito.
6. **Tipos de sprite** (`BACKGROUND`, `BACKNONCOLL`, `NONCOLL`, `BOUNDARY`…, XOR, sombra) vêm de `VidOperator`/`ColOperator` (~400 linhas no
   Felix): é a tabela a transcrever para o rasterizador de software de referência.
7. **Matemática** (`SuzyMath.cpp`): multiplicação 16×16→32 em **44** ticks (**54** com sinal/acumulação); divisão 32÷16 em
   **176 + 14·N** ticks (N = zeros à esquerda do divisor); em multiplicação com sinal, `0x8000` é positivo e `0` é negativo (aviso do
   manual do Lynx); acessar a área de matemática (`$FC50..$FC6F`) enquanto ocupado marca `unsafe` (`SPRSYS` bit 2). **Para o HLE**: calcular na hora
   (é pura aritmética) e manter `mathbusy` por esse tempo — jogos fazem *polling*.
8. **Tempo do desenho** (constantes do Gearlynx, ordem de grandeza): partida do SCB ≈ 35 ticks, linha visível ≈ 60, linha recortada ≈ 46,
   par de pixels ≈ 5, leitura de RAM = 2 ticks. **Uso**: estimar `SPRSYS.busy` a partir da geometria do SCB (já previsto em `docs/03` §4);
   não precisa ser exato, precisa **terminar** e não ser absurdamente curto/longo para jogos sensíveis.
9. **Armadilhas já tratadas pelos emuladores**: *bug* do carregamento do pen map na quebra de página (Felix: `TODO`), leitura de `SPRSYS`
   com `unsafe`, `SPRGO` escrito enquanto ocupado (Gearlynx), reinício durante desenho (Felix: `mResetRequestDuringSpriteRendering`).

**Proposta (M3)**: escrever `lynxtrace/suzy_ref.py` — rasterizador **de referência independente** que implementa os itens 1–6 (a partir
desta especificação, não do código), e comparar o HLE→Cel contra ele quadro a quadro com a métrica de diferença por pixel. É o mesmo
método que validou o tradutor (oráculo independente + teste diferencial). As capturas de analisador lógico do Gearlynx e os *homebrews*
de teste (`laoo_slope_test`) são casos de teste candidatos.

## 6. Cartucho, formatos e boot

* **Cartucho**: endereçamento serial por **registrador de deslocamento** — `CART_ADDR_STROBE` (SYSCTL1 bit 0) com `CART_ADDR_DATA` (IODAT)
  desloca 1 bit; **strobe alto zera o contador de página**; `RCART0/RCART1` leem o byte atual e incrementam o contador; `AUDIN` alterna
  para os bancos "A" (`bank0A/bank1A`) quando o jogo usa 2 bancos. EEPROM e carts "GameDrive/ElCheapo SD" ficam *atrás* do mesmo protocolo.
  → Nosso `lx_overlay` (cartucho serial) deve ser um **objeto cartucho** com `strobe/data/audin/read/ptr`, não um array plano.
* **Cabeçalhos**: `.lnx` (versão 1; tamanhos de página × 256 B, little-endian), **`LNX2`** (magic `LNX2`, 4 bytes de tipo de banco, versão 1 LE,
  nome 32 B, fabricante 16 B, rotação, `flags` [bit 0 = Lynx II], EEPROM, `custom`, `sd_api`) e **BS93** (homebrew; `80 08`, endereço de carga e
  tamanho **big-endian**). `lynx2c ingest` já faz `.lnx` e BS93; **falta LNX2** (barato) e o *banco de jogos por CRC32* do Gearlynx (rotação,
  EEPROM, AUDIN) que o cabeçalho antigo não informa — necessário para a **rotação** do vídeo (jogos verticais) no 3DO.
* **Boot (HLE da ROM de 512 B)** — as 3 armadilhas do Felix (`BootROMTraps.cpp`), que dispensam a imagem de boot:
  1. *Reset*: `IODAT=2`, `IODIR=3`; salta para o *clear*.
  2. *Clear*: zera os 64 KB de RAM, inicializa registradores do Mikey, `$05/$06 ← $0200`, empilha o retorno para o *decrypt*, `A=0`.
  3. *Decrypt*: lê `(256 − SUZY[$B2]) × 51` bytes do cartucho, decifra para `$0200`; estado de saída **`A=0 X=0 Y=2`, `I=1 Z=1`, `N=V=D=C=0`**, salta para `$0200`.
  → **Efeito em R8**: para *commercial*, o `lynx2c` não precisa da ROM de boot: precisa **só do passo de decifração do 1º bloco**
  (o Felix, MIT, faz **RSA-512 com expoente público 3** — `enc³ mod N` — e depois soma acumulada dos bytes, descartando o último; são ~10 linhas
  de inteiros grandes em Python, a reimplementar a partir desta descrição, com crédito no `NOTICE`) e de um estado inicial
  fixo. O 1º estágio decifrado (em `$0200`) é código ordinário a recompilar; os blocos seguintes vêm pelo protocolo serial acima.
  Isso **simplifica o `ingest`** (hoje exige o usuário fornecer a imagem de boot) — tarefa nova.
* **Rotação, EEPROM e cart "banked"** vêm do cabeçalho/BD; um jogo vertical precisa que o 3DO gire o Cel (`HDX/HDY/VDX/VDY` — já temos matriz no CCB, sem custo).

## 7. Padrões de arquitetura úteis (para os *outros consoles*)

| Padrão | Onde | Por que serve a emuladores/portes futuros |
|---|---|---|
| **Núcleo dirigido por eventos em ticks absolutos** (fila de prioridade: disparo de timer, DMA, amostra de áudio, IRQ) | Felix `ActionQueue` | mesma estrutura serve para NES/SMS/Mega Drive: cada chip agenda o *próximo* evento; sem laço por ciclo |
| **CPU como gerador de pedidos de barramento** (fetch/read/write → `Core` resolve por tabela de páginas e cobra o tempo) | Felix `CPU::advance()` | isola temporização de CPU×periférico; o mesmo núcleo de CPU aceita cobrança diferente por console |
| **Tabela de páginas (256 ponteiros/handlers)** reconstruída quando o registro de mapeamento muda | Gearlynx `Memory::RebuildMemoryMap`, Felix `mPageTypes` | leitura/escrita O(1) sem `if` por endereço; é o que o nosso `lx_mem` deveria ter para MAPCTL |
| **Roubo de ciclos** como contador separado (`InjectSuzyStolenCycles`/`ApplyBusStall`) | Gearlynx `Bus` | modelo barato de DMA concorrente; vale para VDP/PPU DMA em outros consoles |
| **Serialização versionada de estado + rebobinar + *run-ahead*** | Gearlynx | exige estado 100 % em structs POD — útil também para depurar o recompilado |
| **Banco de jogos por CRC32** (hardware, rotação, SRAM/EEPROM, mapeador) | Gearlynx `game_db.h` | todo console tem jogos que o cabeçalho não descreve; é a forma padrão de lidar |
| **Testes contra captura de hardware** (analisador lógico `.dsl/.vcd`) e contra ROMs de teste | Gearlynx `tests/`, Felix `laoo_slope_test` | um terceiro tipo de oráculo, **além** do código de outro emulador |
| **Camada fina `run_<console>(rom, len, nome)`** + utilitários de entrada/save/log compartilhados; **memória só alocada ao iniciar o núcleo** | Cardputer `main.cpp`/`share/` | exatamente a forma de um "3DO multi-console": cada console = um módulo com `init/run_frame/deinit`, comum de vídeo (Cel), áudio, controle |
| **API libretro** (`retro_run`, `get_system_av_info`, estado, entrada) como língua franca | libretro-handy | muitos núcleos prontos (NES, SMS, MD, PCE, GB…) com a mesma interface; um *shim* libretro→3DO permitiria **reaproveitar núcleos inteiros** onde AOT não vale a pena (consoles lentos de emular → ARM60 12,5 MHz é o gargalo) |
| **Pular quadros e renderizar sob demanda** | Cardputer `UpdateFrame(drawFrame)` | lógica a taxa própria, vídeo a taxa do display (§4.1) |

**Dado de desempenho útil**: o Cardputer roda o Handy (interpretador) **a velocidade plena** num Xtensa de 240 MHz com *frame skip* e
< 256 KB. O ARM60 do 3DO tem 12,5 MHz (~20× menos relógio): **emular por interpretação é inviável** para o Lynx — confirma a escolha
AOT (D2). Para consoles *muito* mais leves (Game Boy, SG-1000) um núcleo interpretado pode caber; para o resto, AOT + HLE.

## 8. O que muda no roteiro (resumo executável)

Não implementado nesta entrega (só leitura + documentação + 1 ferramenta de cruzamento). Ordem sugerida:

1. **Pequenos, no tradutor**: NOPs multi-byte do Lynx I; `RMB/SMB/BBR/BBS` sob `--lynx2`; cabeçalho `LNX2`; `CB`/`DB` como NOP 1 B/1 c (o Handy os trata como sono; ver §2).
2. **M2**: ticks em vez de ciclos (§3.3), `lx_mikey` com cadeia de 8 timers + IRQ por nível, agendador por próximo evento, vblank real,
   `CPUSLEEP`; lógica×apresentação desacopladas (§4.1); `lx_mem` com tabela de páginas e `MAPCTL`.
3. **`ingest` commercial**: HLE do boot (3 armadilhas), decifração do 1º bloco, objeto cartucho serial (RCART/strobe/AUDIN/bancos),
   BD por CRC32 (rotação/EEPROM).
4. **M3**: `lynxtrace/suzy_ref.py` (oráculo de sprites) + HLE→Cel + colisão por regra exata do depósito + matemática do Suzy + `busy` estimado.
5. **Depois**: áudio (4 canais LFSR), EEPROM/NVRAM no 3DO, fase 2b (`JSR` nativo).
6. **Multi-console**: manter o `lx_platform.h` (vídeo/áudio/entrada/tempo) **independente do Lynx**; cada console novo = módulo
   `core_<console>` com a mesma forma `init/run_frame/deinit` (modelo Cardputer); avaliar o *shim* libretro para núcleos que não se
   beneficiam de AOT.

## 9. Limites desta análise
* Li o **código-fonte**, não executei nenhum emulador; as conclusões de temporização são "o que o código modela", conferidas por pares
  de fontes. Onde as fontes divergem (página cruzada em leitura indexada; fronteira de 16 bytes) está explícito acima.
* Os valores `0x9E`/`0x68` dos timers são **derivados** de 60 Hz, não lidos de uma ROM — conferir no primeiro jogo real.
* Não medi nada em hardware nem no 3DO. O único teste numérico novo é o cruzamento de 178 opcodes (0 divergências) com o Gearlynx.
