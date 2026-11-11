# 02 — Pipeline de tradução AOT (lado PC)

Responde: *como identificar blocos de código 65C02, separar dados puros dos
opcodes e gerar o `.c` final?* Nenhum parser de opcodes é especificado aqui
(próxima etapa, após aprovação); o pipeline só pressupõe um **decoder** com
interface `decode(bytes, addr) -> Insn{len, mnemonic, mode, operand, flow, cycles}`.

## 1. O problema que define a arquitetura

Em 6502/65C02 **não existe separação código/dado e a decodificação não
auto-sincroniza** (varredura linear erra feio). Além disso, no Lynx:

1. O cartucho **não é executável**: um carregador copia segmentos (via
   `RCART0`) para os 64 KB de RAM, reutilizando as mesmas faixas (**overlays**).
2. O estágio de boot de cartuchos comerciais é cifrado (a ROM de boot do Lynx
   decifra); homebrew usa formatos de carga próprios (ex.: cabeçalho BS93).
3. Há `JMP (abs)`, `JMP (abs,X)`, **"RTS trick"** (empilhar endereço−1 e `RTS`),
   tabelas de endereços, dados *inline* após `JSR`, e código que se auto-modifica
   ou é gerado em RAM (rotinas de desenho "compiladas").

Conclusão: **análise estática pura é insuficiente**. A arquitetura é
**estática guiada por perfil dinâmico + anotação humana (manifest)**.

## 2. Modelo de evidências para classificar bytes

Cada byte de cada segmento recebe um rótulo; três fontes de evidência:

| Fonte | Evidência | Peso |
|---|---|---|
| **Execução** (trace do estágio B) | PC executado; bytes de opcode/operando realmente buscados | **verdade** |
| **Alcançabilidade estática** | descida recursiva a partir de seeds | provável |
| **Referência de dados** | operandos de `LDA abs,X`, ponteiros ZP, SCB/`SPRDLINE`, tabelas, leituras de `RCART0` | dado |

Rótulos: `CODE_OP`, `CODE_ARG`, `DATA_RO`, `DATA_SPRITE`, `DATA_ADDRTAB`,
`DATA_INLINE`, `UNKNOWN`. Regras de resolução, em ordem:

1. Executado no trace ⇒ `CODE_OP/CODE_ARG` (inabalável).
2. Alcançável estaticamente e **nunca** referenciado como dado ⇒ `CODE_PROBABLE`
   (traduzido na forma **cold**; relatado em `report.md`).
3. Referenciado como dado e não executado ⇒ `DATA_*`.
4. **Sobreposição** (opcode de uma instrução cai no operando de outra): se ambas
   foram executadas ⇒ salto desalinhado ou **SMC**; vai para `unresolved.json` e
   exige decisão no manifest. Se só uma foi executada, ela vence.
5. Opcode ilegal/indefinido em caminho estático ⇒ o caminho é **podado** (provável
   dado) com aviso. Nunca se "adivinha" tradução de opcode inválido.
6. Varredura linear é usada **apenas** como mapa de calor diagnóstico, nunca
   para classificar.

Padrões que o analisador reconhece e o manifest pode forçar:

- **Tabela de saltos**: `LDA lo,X / PHA / LDA hi,X / PHA / RTS`, `JMP (tab,X)` →
  entradas viram seeds; vetor de endereços vira `DATA_ADDRTAB`.
- **Dados inline após `JSR`** (`JSR print / .byte "OLA",0`): o callee desempilha o
  endereço de retorno. Detectado quando o callee faz `PLA/PLA` seguido de leitura
  indireta; o manifest informa o terminador (`[[inline_data_call]]`).
- **Operando modificado** (`STA self+1`): marcado `smc`; política no manifest
  (`param_operand` | `forbid` | `hook`) — ver §6.

## 3. Estágios

### A. `ingest`
Lê `.lnx` (cabeçalho de 64 bytes: magic `LYNX`, tamanhos de página dos bancos 0/1,
versão, nome, fabricante, **rotação**, EEPROM). Produz `CartImage` + SHA-256
(amarra manifest ↔ ROM). O estágio de boot cifrado **não** é decifrado pelo
projeto: o usuário fornece a imagem de boot (ROM do Lynx, que ele possui) apenas
ao `lynxtrace`; o resultado **não a contém** (o HLE substitui o boot).

### B. `lynxtrace` — perfil dinâmico
Executa a ROM num núcleo 65C02 de referência (interpretador **no PC**, que também
serve de oráculo nos testes) com entradas gravadas (replay), por N quadros.
Registra, em `trace.bin`:

- conjunto de PCs executados + bytes buscados (detecta SMC por mudança de bytes);
- alvos de `JMP` indireto, e `RTS` cujo destino ≠ retorno do `JSR` correspondente;
- **carga de segmentos**: correlação *leitura de `RCART0` → escrita em RAM* ⇒ tuplas
  `(cart_offset, load_addr, len)` ⇒ overlays;
- escritas em Suzy: endereços de SCB, `SPRDLINE`, tipos, bpp, `VIDBASE`;
- leituras de E/S em *polling* (candidatas a ponto de sincronismo);
- contagem por bloco ⇒ **hot/cold**.

Cobertura incompleta é esperada; o trace **semeia**, a descida recursiva **expande**,
e o `unresolved.log` gerado em T3 (`lx_unresolved`) realimenta o ciclo.

### C. `discover` — CFG + classificação
```
seeds := vetores do jogo ∪ entradas do manifest ∪ PCs do trace ∪ alvos de jump table
para cada overlay O (segmentos do §B ∪ manifest):
    worklist := seeds ∩ O
    enquanto worklist ≠ ∅:
        a := pop;  se visitado ou fora de O: continue
        i := decode(O[a]);  se ilegal: podar, avisar; continue
        marcar bytes [a, a+len) como CODE_OP/ARG; registrar xrefs de dado do operando
        conforme i.flow:
            seq        -> push a+len
            branch     -> push alvo, push a+len                    (Bcc, BRA)
            jmp abs    -> push alvo                                  (fim de bloco)
            jmp ind    -> alvos do trace/jump table; senão: marca "dinâmico"
            jsr        -> push alvo (nova rotina), push a+len (continuação, LX_DE_RETADDR)
            rts/rti/brk-> fim de bloco
formar blocos básicos: líderes = entradas, alvos, após branch, após JSR
formar rotinas: alcançabilidade intra-procedural a partir de cada alvo de JSR
aplicar regras de resolução do §2; escrever classmap.bin, cfg.json, report.md
```
Saída determinística (ordenação por `(overlay, addr)`).

### D. `lift` — IR
Cada instrução vira micro-operações explícitas com **definição de flags** declarada
(`defs: N Z C V`), leitura (`uses`), região de memória do operando
(`RAM | SUZY | MIKEY | ROMVEC | DYNAMIC`) e custo em ciclos (inclui +1 de
cruzamento de página onde aplicável, tratado como pior caso ou como teste dinâmico
no *cold tier*). Cobre também o *subset* exato do núcleo (confirmar se o Lynx tem
`BBR/BBS/RMB/SMB` da Rockwell e `WAI/STP`; **não presumir**).

### E. `optimize`
1. **Vivacidade de flags** (backward, por bloco + entre blocos): só materializa N/Z/C/V
   lidos adiante. É a otimização mais valiosa.
2. **Resolução de região** de cada acesso: absoluto → direto; ZP/pilha → RAM; indexado
   → `lx_rd8/lx_wr8` (uma comparação).
3. Propagação de constantes entre blocos de uma rotina; remoção de armazenamentos mortos
   nos registradores.
4. **Hot tier** (inline, A/X/Y em registradores ARM dentro da rotina) para blocos
   quentes do trace; **cold tier** (sequência compacta de chamadas a helpers por
   opcode; ainda AOT, **não** é interpretador) para o resto — controla o tamanho (§7 de `04`).
5. Fusão em **rotinas com entradas** (fase 2, ver §7).

### F. `emit` — gerar C89
- Um `.c` por *chunk* de overlay (≤ ~2000 blocos por arquivo, para compilar rápido no armcc).
- Nomes estáveis: `lx_ov03_a1b2` (overlay 3, endereço $A1B2).
- Cada bloco carrega `#line` apontando para `overlay:endereço` e, opcionalmente, o
  *disassembly* original em comentário; `game.map` mapeia endereço ↔ símbolo.
- Dados puros **não** viram vetores C (compilar 512 KB de array no armcc é lento e
  desperdiça): ficam em `lxdata.bin` carregado do disco no boot.
- `lx_tables.c`: tabelas de despacho (`LxDispatchEntry[]`, ordenadas) **só** com
  entradas alcançáveis dinamicamente; `lx_program.c`: `LxProgram`, overlays, hooks.
- `lx_game_config.h`: `LX_FB_MODE`, `LX_COLL_MODE`, `LX_SPRITE_SCHED`, limites.
- O código gerado confere `LX_ABI_VERSION` em tempo de compilação.

### G. `spritecook`
A partir dos SCBs/`SPRDLINE` vistos no trace (e achados estaticamente em
`DATA_SPRITE`), converte os dados de linha do Suzy (RLE de 1–4 bpp com *offset* por
linha) em Cel "packed" do 3DO (também RLE por linha — conversão quase 1:1 e **sem
inflar a RAM**) + índice `cart_offset → cel` em `lxdata.idx`. Sprites gerados em
tempo de execução ficam para o caminho de *runtime cache* do HLE.

### H. `pack3do`
Gera o `Makefile` do SDK, a árvore de arquivos do disco (executável + `lxdata.bin` +
`lxdata.idx`) e a ISO. Nomes exatos das ferramentas do SDK a conferir na doc oficial.

## 4. Manifest do jogo (`games/<jogo>/manifest.toml`)
Humano-no-laço: entradas, overlays conhecidos, hooks HLE, tabelas de salto, dados
inline, SMC, modos do Suzy, orçamento. Esquema em `games/_template/manifest.toml`.

## 5. Tratamento de RAM, pilha e E/S
- RAM Lynx = `lx_u8 lx_ram[65536]` (64 KB da DRAM do 3DO).
- `JSR`: empilha (endereço−1) **na pilha emulada** e chama a rotina C; `RTS`: desempilha e
  compara — se bater com o chamador C, `return` nativo; senão `lx_dispatch()`.
- Acessos a `$FC00–$FCFF` → `lx_suzy_*`; `$FD00–$FDFF` → `lx_mikey_*`; `$FFF9` (MAPCTL)
  trata sobreposição de ROM/vetores.

## 6. Código auto-modificável e gerado em RAM
Política por região: **(a)** `param_operand` — o byte modificado vira variável lida de
`lx_ram` em cada execução (cobre `STA self+1`); **(b)** `hook` — rotina substituída por
HLE nativo (descompressores, rotinas de desenho em RAM); **(c)** `forbid` — erro de
tradução. Código **gerado em tempo de execução** (não existe no cartucho) **não pode**
ser AOT: exige hook. Ver decisão D2 em `05`.

## 7. Modelo de geração (fases)
- **Fase 1 (corretude):** um bloco básico = uma função `lx_u32 f(LxCpu*)`; retorno = próximo PC
  ou código especial; trampolim `lx_run`. Simples, verificável, lento.
- **Fase 2 (desempenho):** rotinas com *goto* interno e entradas múltiplas; A/X/Y em
  registradores; chamadas diretas para `JSR` estático. A ABI do runtime não muda.

## 8. Erros em T3
`lx_unresolved(pc)`: grava PC, overlay ativo, `S` e últimos N PCs em `unresolved.log` →
`lynx2c --seed unresolved.log` reprocessa. Nunca "tenta executar" bytes sem tradução.

## 9. Verificação (sem ela, nenhum opcode entra)
1. **Diferencial por instrução**: cada opcode × amostra exaustiva de registradores/flags/
   operandos, tradução compilada no host vs. núcleo de referência.
2. **Suítes funcionais conhecidas de 6502/65C02** (ex.: testes de Klaus Dormann), passadas
   pelo pipeline completo e executadas no host.
3. **Jogo inteiro**: hash do estado (RAM + regs) a cada vblank, host-traduzido vs. referência.
4. **3DO**: emulador de 3DO e, depois, hardware real; compara capturas de tela.
5. Teste de **determinismo** (duas execuções do tradutor ⇒ bytes idênticos).
