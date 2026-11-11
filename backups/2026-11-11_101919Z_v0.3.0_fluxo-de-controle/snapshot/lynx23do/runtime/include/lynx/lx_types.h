/*
 * lx_types.h — tipos e macros portáveis do runtime Lynx→3DO.
 *
 * Restrições de portabilidade (valem para TODO header/fonte do runtime E
 * para o código gerado pelo lynx2c):
 *   - C89/ANSI (armcc do SDK 3DO): sem //, sem declarações no meio de bloco,
 *     sem long long, sem stdint.h, sem designated initializers, sem inline C99.
 *   - O ARM60 do 3DO roda BIG-ENDIAN; o 65C02 é little-endian. Por isso a RAM
 *     do Lynx é SEMPRE um vetor de bytes e todo acesso de 16 bits é composto
 *     de dois acessos de 8 bits (nunca cast de ponteiro para u16/u32).
 *   - ARMv3 (ARM60) não tem LDRH/STRH: evitar u16 em estruturas quentes
 *     quando um u32 resolve.
 */
#ifndef LX_TYPES_H
#define LX_TYPES_H

typedef unsigned char   lx_u8;
typedef signed char     lx_s8;
typedef unsigned short  lx_u16;
typedef signed short    lx_s16;
typedef unsigned int    lx_u32;   /* int = 32 bits em ARM60 e no host */
typedef signed int      lx_s32;

/* verificação de tamanhos em tempo de compilação (C89: array de tamanho negativo) */
typedef char lx_chk_u8 [(sizeof(lx_u8)  == 1) ? 1 : -1];
typedef char lx_chk_u16[(sizeof(lx_u16) == 2) ? 1 : -1];
typedef char lx_chk_u32[(sizeof(lx_u32) == 4) ? 1 : -1];

/* inline portável (armcc: __inline; gcc/clang em -std=c89: __inline__) */
#if defined(__ARMCC_VERSION) || defined(__CC_NORCROFT)
#  define LX_INLINE static __inline
#elif defined(__GNUC__)
#  define LX_INLINE static __inline__
#else
#  define LX_INLINE static
#endif

/* ponto-fixo usado na tradução para Cels (ver lx_cel.h) */
typedef lx_s32 lx_fix16;   /* 16.16 */
typedef lx_s32 lx_fix20;   /* 12.20 */

#define LX_ARRAY_LEN(a) ((lx_u32)(sizeof(a) / sizeof((a)[0])))

#endif /* LX_TYPES_H */
