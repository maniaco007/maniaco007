# 15 — Roteiro estruturado de trabalho (orquestrador + subagentes)

Para a sessão **local** (Claude Code no PC). Este documento é o contrato de trabalho: marcos (F0–F10), quem faz cada um, critérios de aceitação
**mensuráveis**, o que depende de você e como não perder a confiança no que é entregue.
Rótulos de esforço: **S** (horas), **M** (uma a poucas sessões), **L** (várias sessões, com risco). São ordens de grandeza, não promessas.

## 1. Papéis
A **sessão principal é o orquestrador**: planeja, delega, **reexecuta as verificações por conta própria** e decide. Os subagentes ficam em `.claude/agents/`.

| Subagente | Modelo | Responsabilidade | Escreve em |
|---|---|---|---|
| `guardiao-processo` | sonnet | backup obrigatório (abrir), checklist (fechar), licenças, documentação, higiene de commit | `CLAUDE.md`, `docs/`, `NOTICE`, scripts de verificação |
| `avaliador-projetos` | opus | avaliação **só leitura** dos projetos NES/SMS do usuário; o que reaproveitar | só `docs/14-avaliacao-projetos-nes-sms.md` |
| `integrador-3do-armcc` | sonnet | compilar com `armcc`, ISO, primeiro teste no ODE, medição no console | `runtime/platform/3do/**`, `docs/11` |
| `engenheiro-tradutor` | opus | `lynx2c` e oráculo `core65c02.py`: ticks, fase 2b, opcodes | `pc-tools/lynx2c/**`, `pc-tools/lynxtrace/lynxtrace/core65c02.py`, testes do tradutor |
| `engenheiro-mikey-agendador` | opus | M2: ticks, timers, IRQ, vblank, `CPUSLEEP`, `MAPCTL`, páginas | `runtime/src` (tempo/mikey/mem), headers correspondentes, oráculo de timers |
| `engenheiro-suzy-hle` | opus | M3: oráculo de sprites, HLE SCB→Cel, colisão, matemática, `spritecook` | `runtime/src/lx_suzy*`, `pc-tools/spritecook`, `pc-tools/lynxtrace/suzy_ref.py` |
| `engenheiro-cartucho-boot` | sonnet | HLE do boot, cartucho serial, BD por CRC32, EEPROM | `ingest.py`, `lx_overlay.c`/`lx_cart*`, testes de ingest |
| `verificador-independente` | opus | revisão adversarial; **não edita** | (nada; só relatório) |
| `arquiteto-multiconsole` | sonnet | arquitetura para outros consoles; **não implementa** | só `docs/16-arquitetura-multiconsole.md` |

Comandos (`.claude/commands/`): `/status-projeto`, `/disparar-marco <F#>`, `/abrir-lote`, `/fechar-lote`, `/verificar-tudo`.

## 2. Ciclo padrão de cada marco (não pular passos)
1. **`/abrir-lote`**: `guardiao-processo` cria o backup (regra do usuário) e confirma árvore limpa; você confere dependências do marco.
2. **Plano curto** (você aprova antes de qualquer edição).
3. **Implementação** pelo subagente responsável, com o *prompt de disparo* do marco (§5). Oráculo/teste primeiro, código depois.
4. **Verificação do implementador** (comandos da §3, com saída real).
5. **`verificador-independente`** reexecuta tudo, caça testes fracos e planta mutantes **próprios**.
6. **`/fechar-lote`**: `guardiao-processo` (backups íntegros, docs com números reais, licenças, commit). Commit **só com a sua confirmação**; `git push` só quando você mandar.
7. Atualize a coluna **Estado** da §5 (marco → "feito e verificado em <data>, commit <hash>") e o que ficou **não verificado**.

## 3. O que rodar conforme o tipo de mudança
| Mudou… | Rodar |
|---|---|
| `pc-tools/lynx2c`, `lynxtrace`, `optable` | unitários (hoje 149) + `run_diff.sh` (0 falhas, -O0/-O2) + `run_dormann.sh` (2 PASSAM) + mutação nos trechos novos |
| `runtime/src`, `runtime/include` | `run_diff.sh` + `check_headers.sh` + `make host-check` (demo) + `check_3do_build.sh` |
| `runtime/platform/3do` | `check_3do_build.sh` + `check_headers.sh`; compilar com `armcc`; **teste no ODE pelo usuário** |
| `ingest`, cartucho | unitários + testes de ingest/protocolo com dados **sintéticos** + mutação |
| somente docs | conferir que cada número citado coincide com a saída real |
| sempre | `scripts/check_backups_immutable.sh` (OK) |

## 4. Paralelismo e conflitos
Cada agente tem **donos de arquivo** (tabela da §1). Dois agentes **não** editam o mesmo arquivo ao mesmo tempo. Mudança de ABI (`lx_cpu_abi.h`, `LX_ABI_VERSION`) é **sempre** coordenada
por você, com tradutor e runtime juntos.
- **Podem andar em paralelo:** F1 ∥ F4 ∥ F6 ∥ F10 (áreas disjuntas); F2 ∥ F4.
- **Em série:** F4 → F5 (o runtime usa o modelo de ticks do tradutor); F5 → F7; F1/F2 → F3.
- **Isolamento:** para paralelismo real use *git worktrees* (`git worktree add ../lynx23do-F4 -b f4-ticks`), um por agente; cada um cria o seu backup com *slug* próprio; você integra e reroda tudo.
- Trava técnica da regra de backups: `scripts/claude-hooks/README.md` (opcional, ativação sua).

## 5. Marcos

| # | Marco | Responsável | Depende de | Esforço | Estado |
|---|---|---|---|---|---|
| F0 | Baseline no PC | `guardiao-processo` + você | — | S | **pendente** |
| F1 | Avaliação dos projetos NES/SMS | `avaliador-projetos` | F0 | M | **pendente** |
| F2 | M1 no console (barras no ODE) | `integrador-3do-armcc` + você | F0 (F1 recomendado) | M | **pendente** |
| F3 | Reaproveitar backend/ISO/entrada/áudio dos seus projetos | `integrador-3do-armcc` | F1, F2 | M | pendente |
| F4 | Tradutor em ticks de 16 MHz | `engenheiro-tradutor` | F0 | M | pendente |
| F5 | M2: Mikey, timers, IRQ, vblank, agendador | `engenheiro-mikey-agendador` | F4 | L | pendente |
| F6 | Cartucho serial + HLE do boot + BD por CRC32 | `engenheiro-cartucho-boot` | F0 | M | pendente |
| F7 | M3: Suzy (oráculo, HLE→Cel, colisão, matemática) | `engenheiro-suzy-hle` | F5, F2 | L | pendente |
| F8 | Áudio (4 canais) e EEPROM/NVRAM | `engenheiro-mikey-agendador` + `engenheiro-cartucho-boot` + `integrador-3do-armcc` | F5, F3 | L | pendente |
| F9 | Desempenho real no ARM60 e fase 2b (JSR/RTS nativos) | `engenheiro-tradutor` + `integrador-3do-armcc` | F2, idealmente F7 | L | pendente |
| F10 | Arquitetura multi-console | `arquiteto-multiconsole` | F1 | M | pendente |
| — | v0.1–v0.8: tradutor, oráculo, runtime M1, backend 3DO (estático), survey, modelos de CPU | (sessão de nuvem) | — | — | **feito**; falta rodar no console |

### F0 — Baseline no PC
- **Objetivo:** provar que o repositório baixado se comporta no PC como na nuvem; ativar a trava de backups (opcional).
- **Aceitação:** `/verificar-tudo`: 149 unitários OK; `run_diff.sh` 0 falhas (909 852 + 13 920 vetores); Dormann: 2 PASSAM; `check_headers.sh` OK; `check_backups_immutable.sh` OK;
  registrado em `docs/13` o SO, versões de `python3`/`gcc`/`clang` e o caminho do devkit. Qualquer divergência é um achado a investigar antes de seguir.
- **Prompt:** `Rode /verificar-tudo e registre em docs/13 (nova seção "Baseline no PC") o ambiente e as contagens reais. Não altere código. Se algo divergir do esperado, pare e reporte.`

### F1 — Avaliação dos projetos NES/SMS (só leitura)
- **Entrega:** `docs/14-avaliacao-projetos-nes-sms.md` (tabela comparativa, **receita de ISO aceita pelo ODE passo a passo**, lista priorizada de reaproveitamento com esforço/risco, perguntas, o que não foi verificado).
- **Aceitação:** cada afirmação com `arquivo:linha`; fps **medido** separado de afirmado; nenhuma alteração nas pastas do usuário (confira com `git status`/`diff` nelas se forem repositórios); licenças de terceiros listadas.
- **Prompt:** `Use o subagente avaliador-projetos para avaliar, SOMENTE LEITURA, as pastas <caminho NES> e <caminho SMS> e produzir docs/14-avaliacao-projetos-nes-sms.md conforme o protocolo dele. Antes, pergunte-me o fps medido no console e quais jogos testei.`

### F2 — M1 no console
- **Aceitação (você executa a parte física):** `make host-check` imprime `quadros=8 sprgo_ignorados=0`; `make DEVKIT=…` gera `lynx23do.iso` sem erro; **o ODE aceita o ISO**; na tela: 16 barras 320×204 centradas, e os 2 primeiros pixels mudam ao apertar botões.
  `docs/11` ganha as lições (erros do `armcc` e correções). `check_3do_build.sh` e `check_headers.sh` continuam OK.
- **Se falhar:** o agente relata a **primeira** mensagem de erro e hipóteses ordenadas; a tabela sintoma→causa está em `docs/11` §6.
- **Prompt:** `Use o subagente integrador-3do-armcc: ative o devkit em <caminho>, rode make host-check e make DEVKIT=<caminho> em lynx23do/runtime/platform/3do, corrija o backend até compilar, gere o ISO e me diga exatamente o que devo ver no ODE. Use a receita de ISO de docs/14 se existir.`

### F3 — Reaproveitamento
- **Aceitação:** a camada `lx_platform` (vídeo/entrada/tempo/arquivo) reaproveita o que já funciona nos seus projetos; demo a 60 fps estável **medido**; licenças confirmadas por você e creditadas em `NOTICE`; nada copiado sem sua confirmação.
- **Prompt:** `Use o subagente integrador-3do-armcc para aplicar o item <N> da lista de reaproveitamento de docs/14 ao backend 3DO. Licença confirmada pelo usuário: <sim/não e qual>. Medir o fps no console antes e depois.`

### F4 — Tradutor em ticks
- **Objetivo:** custo estático por instrução `4·bytes + 5·(ciclos−bytes)` (+ decimal, desvio tomado, cruzamento); fim do `LX_CYCLES_PER_FRAME` fica para F5.
- **Aceitação:** oráculo `core65c02.py` com o mesmo modelo, escrito **por regra** (fonte independente: `docs/12` §3, modelo por acesso do Felix); diferencial 0 falhas; Dormann PASSA; ≥ 4 mutantes mortos;
  `docs/12` §3.3 itens 1 e 4 marcados como feitos; ABI só muda se necessário e então com `LX_ABI_VERSION` revisto.
- **Prompt:** `Use o subagente engenheiro-tradutor para implementar o modelo de ticks de docs/12 §3.3 (itens 1 e 4) no lynx2c e no oráculo, seguindo a disciplina dele. Não mexa no runtime além de constantes de ABI, que devem ser coordenadas comigo.`

### F5 — M2 (Mikey/agendador)
- **Aceitação:** oráculo de timers em Python (por regra); diferencial C×oráculo para encadeamento, reload, prescales, IRQ mascarado e `CPUSLEEP`; vblank real como *borrow* do timer 2; quadro dirigido pelos timers
  (um jogo a 75 Hz roda a 75 Hz de lógica); `6502_interrupt_test` do Dormann passa; demo com IRQ de vblank no host; ≥ 4 mutantes mortos; `check_3do_build.sh` OK.
- **Prompt:** `Use o subagente engenheiro-mikey-agendador para implementar o M2 conforme docs/12 §3–§4 e docs/15 F5. Primeiro o oráculo de timers em lynxtrace, depois o C. F4 já está feito (tradutor em ticks).`

### F6 — Cartucho e boot
- **Aceitação:** `ingest` de um `.lnx` **sintético** (gerado nos testes) executa o HLE do boot (decifra o 1º bloco com chave **de teste**), produz a imagem pós-boot e o `lynx2c build` traduz o 1º estágio; objeto cartucho serial com testes contra modelo
  independente; BD por CRC32 para rotação/EEPROM/AUDIN; nenhum dado de jogo no repositório; ≥ 4 mutantes mortos.
- **Observação:** com um cartucho **seu** de verdade o teste final é local e **nunca** vai ao repositório.
- **Prompt:** `Use o subagente engenheiro-cartucho-boot para implementar o HLE do boot e o objeto cartucho serial (docs/12 §6). Tudo com dados sintéticos; sem ROMs no repositório.`

### F7 — M3 (Suzy)
- **Sub-etapas:** (a) oráculo `suzy_ref.py` por especificação → (b) `spritecook` → (c) HLE SCB→CCB com classes NATIVE/APPROX/FALLBACK → (d) colisão e matemática.
- **Aceitação:** limiares de erro por pixel **definidos antes** de olhar o resultado (registrados em `docs/03`); comparação quadro a quadro host-vs-oráculo; erro medido por classe; matemática bit-exata (44/54 ticks; 176+14N); ≥ 4 mutantes por módulo; demo de sprites no console (você valida).
- **Prompt:** `Use o subagente engenheiro-suzy-hle começando APENAS pela sub-etapa (a): o oráculo suzy_ref.py a partir da especificação de docs/12 §5, com testes e mutação. Pare e relate antes de iniciar (b).`

### F8 — Áudio e EEPROM
- **Aceitação:** modelo dos 4 canais LFSR validado contra o oráculo (por regra) e contra amostras de referência; saída no 3DO por audio folio (decisão com o usuário após `docs/14`); EEPROM 93C46–86 com arquivo/NVRAM; teste de "salvar e recarregar".
- **Prompt:** `Use engenheiro-mikey-agendador para o modelo de áudio (oráculo e C) e engenheiro-cartucho-boot para a EEPROM; depois integrador-3do-armcc para a saída de áudio no 3DO. Em série, nessa ordem.`

### F9 — Desempenho e fase 2b
- **Aceitação:** custo **medido** no ARM60 (ciclos por quadro, por jogo/demo, método registrado); fase 2b com chamadas nativas e a meta de expansão ≤ 10× avaliada com `lynx2c report`; diferencial e Dormann verdes; nenhuma estimativa apresentada como medida.
- **Prompt:** `Use engenheiro-tradutor para a fase 2b (JSR/RTS nativos) com a disciplina de sempre e integrador-3do-armcc para medir antes/depois no console. Reporte números reais e o método.`

### F10 — Multi-console
- **Aceitação:** `docs/16-arquitetura-multiconsole.md` com interface `core_<console>`, números rotulados (medido/calculado/suposto), plano em marcos por console e decisão AOT × interpretado × shim libretro; licenças registradas; perguntas ao usuário.
- **Prompt:** `Use o subagente arquiteto-multiconsole para propor a arquitetura multi-console a partir de docs/12 §7 e docs/14. Só documentação.`

## 6. Confiança e relatórios
- Todo subagente termina com: **o que mudou**, **comandos executados com as contagens reais**, **mutantes plantados (e se morreram)**, **o que não foi verificado**, riscos.
- **Você (orquestrador) não repassa números de agente sem reexecutar.** O `verificador-independente` é obrigatório antes de qualquer commit de código.
- Hardware/tempo: separe sempre **auto-consistência** (C×oráculo) de **comparação externa** (ROM de teste, captura, outro emulador, console real).
- "Não verificado" é uma resposta válida e esperada; "provavelmente ok" não é.

## 7. O que só você pode fazer (portões)
1. Colar/indicar os caminhos dos projetos NES/SMS e responder fps, jogos testados e receita do ISO (F1).
2. Rodar o ISO no ODE e descrever o resultado (F2, F3, F7, F8, F9).
3. Confirmar licenças de qualquer código seu/de terceiros antes de copiá-lo (F3).
4. Decidir: jogos-alvo, cartuchos > ~384 KB (rejeitar × *streaming*), onde salvar NVRAM, meta de fps (docs/13 §6).
5. Autorizar commits, `git push` e a ativação da trava de backups (`scripts/claude-hooks/README.md`).
