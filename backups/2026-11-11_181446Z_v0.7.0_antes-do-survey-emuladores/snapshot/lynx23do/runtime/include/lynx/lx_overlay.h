/*
 * lx_overlay.h — cartucho, overlays de código e hooks HLE.
 *
 * Por que overlays: jogos comerciais do Lynx NÃO executam do cartucho. Um
 * carregador copia segmentos do cartucho (lido em série via RCART0) para a
 * RAM de 64 KB, e a mesma faixa de RAM é reutilizada por segmentos diferentes
 * ao longo do jogo. Logo, "endereço 65C02" não identifica código de forma
 * única: a identidade é (overlay, endereço).
 *
 * O lynx2c descobre os overlays (manifest + trace dinâmico, docs/02 estágio B/C)
 * e emite, por overlay, uma tabela de despacho com SOMENTE os pontos de entrada
 * alcançáveis dinamicamente (alvos de JMP indireto, endereços de retorno após
 * JSR, vetores, hooks). Chamadas/saltos estáticos viram chamadas C diretas e
 * não ocupam tabela.
 */
#ifndef LX_OVERLAY_H
#define LX_OVERLAY_H

#include "lx_types.h"
#include "lx_config.h"
#include "lx_cpu_abi.h"

/* Entrada de despacho (8 bytes no ARM32). Vetor ORDENADO por addr (busca binária). */
typedef struct LxDispatchEntry {
    lx_u16   addr;       /* endereço 65C02 do líder */
    lx_u16   sub_flags;  /* bits 3..0: LX_DE_*; bits 15..4: sub-entrada (líder dentro da rotina 'fn'; 0 = raiz) */
    LxCodeFn fn;
} LxDispatchEntry;
#define LX_DE_FLAGS_MASK 0x000F
#define LX_DE_SUB(x)     ((lx_u32)((x) >> 4))

#define LX_DE_COLD     0x0001  /* gerado na forma compacta (cold tier) */
#define LX_DE_RETADDR  0x0002  /* continuação após JSR (retorno por RTS dinâmico) */
#define LX_DE_VECTOR   0x0004  /* RESET/NMI/IRQ */

typedef struct LxOverlay {
    lx_u16  id;
    lx_u16  load_addr;          /* onde o conteúdo reside na RAM Lynx           */
    lx_u32  size;               /* bytes (<= 65536 - load_addr; u32 p/ caber 65536 em imagens de teste) */
    lx_u16  n_entries;
    lx_u32  cart_offset;        /* offset do conteúdo na imagem do cartucho     */
    lx_u32  content_crc32;      /* checagem opcional (LX_DEBUG) do que foi carregado */
    const LxDispatchEntry *entries;
} LxOverlay;

/* ---- Cartucho (somente leitura, na DRAM do 3DO; lido do disco no boot) -------- */
typedef struct LxCart {
    const lx_u8 *data;          /* imagem sem o cabeçalho .lnx de 64 bytes */
    lx_u32       size;
    lx_u32       bank0_page_size;   /* bytes por página (do cabeçalho .lnx) */
    lx_u32       bank1_page_size;
    lx_u8        rotation;      /* 0 nenhuma, 1 esquerda, 2 direita */
} LxCart;

/* ---- Ciclo de vida do programa gerado --------------------------------------- */
typedef struct LxHook LxHook;
typedef lx_u32 (*LxHookFn)(LxCpu *cpu);   /* mesma convenção de LxCodeFn */

/* Substitui UMA rotina do jogo por implementação nativa (HLE de rotina):
 * carregador de segmentos, memcpy/memset, descompressores, desenho de texto. */
struct LxHook {
    lx_u16   overlay_id;        /* 0xFFFF = vale em qualquer overlay */
    lx_u16   addr;              /* entrada da rotina substituída */
    LxHookFn fn;
    const char *name;           /* p/ log/diagnóstico */
};

/* Descritor do jogo inteiro: emitido pelo lynx2c em lx_program.c */
typedef struct LxProgram {
    const char     *game_name;
    lx_u32          abi_version;       /* deve == LX_ABI_VERSION */
    lx_u16          reset_overlay;
    lx_u16          n_overlays;
    const LxOverlay *overlays;
    lx_u16          n_hooks;
    const LxHook   *hooks;
    lx_u32          cart_size;         /* conferência contra LxCart.size */
} LxProgram;

extern const LxProgram lx_program;     /* definido pelo código gerado */

/* ---- API do runtime -------------------------------------------------------------- */
int  lx_overlay_init(const LxCart *cart);

/* Chamada pelo hook do carregador (ou pelo trampolim em RTS/JMP para dentro
 * de região sem overlay ativo): copia cart[cart_off..+len) -> lx_ram[dest..]
 * e marca o overlay ativo na faixa. Invalida overlays sobrepostos. */
void lx_overlay_load(lx_u16 overlay_id, lx_u32 cart_off, lx_u16 dest, lx_u16 len);

/* Marca 'ov' como ativo na sua faixa (SEM copiar bytes) e desativa overlays
 * sobrepostos. lx_overlay_load() = cópia + lx_overlay_activate(). Também usado
 * por testes no host, onde o conteúdo da RAM é montado pelo próprio teste. */
void lx_overlay_activate(const LxOverlay *ov);
void lx_overlay_reset(void);                 /* nenhum overlay ativo */

/* Overlay ativo que contém 'addr' (NULL se nenhum). */
const LxOverlay *lx_overlay_at(lx_u16 addr);

/* Procedência: dado um endereço da RAM, qual offset do cartucho originou o
 * byte? Retorna -1 se desconhecido/dinâmico (ex.: dado descomprimido).
 * Usado pelo HLE do Suzy para achar sprites já "cozidos" (lx_suzy.h). */
lx_s32 lx_overlay_cart_offset_of(lx_u16 addr);

/* Procura hook para (overlay ativo, addr); NULL se não houver. */
const LxHook *lx_hook_find(lx_u16 addr);

/* ---- Cartucho serial (Suzy RCART0/RCART1) ------------------------------------------ */
/* Modelo do hardware: contador de endereço + registrador de deslocamento. Uma
 * leitura de RCART0 devolve o byte atual e avança o contador; escritas em
 * SYSCTL1/bit de strobe (Mikey/Suzy) reposicionam. Mantido fiel porque o
 * carregador do jogo é código traduzido normal (a menos que haja hook). */
void   lx_cart_reset_counter(lx_u32 bank, lx_u32 page);
lx_u8  lx_cart_read(lx_u32 bank);          /* leitura de RCART0/1 com auto-incremento */
void   lx_cart_strobe(lx_u8 level);        /* linha de strobe de endereço */

#endif /* LX_OVERLAY_H */
