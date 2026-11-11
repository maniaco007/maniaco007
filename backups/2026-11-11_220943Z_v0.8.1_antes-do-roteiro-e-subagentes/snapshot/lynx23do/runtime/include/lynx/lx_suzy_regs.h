/*
 * lx_suzy_regs.h — mapa de registradores do Suzy ($FC00-$FCFF) e campos de bits.
 *
 * ATENÇÃO — origem dos valores: transcritos de memória do "Atari Lynx Hardware
 * Reference" / código do emulador Handy. Itens marcados [VERIFY] DEVEM ser
 * conferidos contra a documentação oficial antes de serem usados pelo HLE
 * (parte do estágio "especificação" aprovado antes de implementar o Suzy).
 */
#ifndef LX_SUZY_REGS_H
#define LX_SUZY_REGS_H

/* ---- Registradores de sprite (pares L/H little-endian) ---------------------- */
#define LX_R_TMPADR     0xFC00  /* endereço temporário                        */
#define LX_R_TILTACUM   0xFC02  /* acumulador de tilt                         */
#define LX_R_HOFF       0xFC04  /* offset horizontal da tela                  */
#define LX_R_VOFF       0xFC06  /* offset vertical da tela                    */
#define LX_R_VIDBAS     0xFC08  /* base do buffer de vídeo (destino do desenho) */
#define LX_R_COLLBAS    0xFC0A  /* base do buffer de colisão                  */
#define LX_R_VIDADR     0xFC0C  /* endereço de vídeo corrente                 */
#define LX_R_COLLADR    0xFC0E  /* endereço de colisão corrente               */
#define LX_R_SCBNEXT    0xFC10  /* próximo SCB (0 na parte alta => fim)       */
#define LX_R_SPRDLINE   0xFC12  /* início dos dados do sprite                 */
#define LX_R_HPOSSTRT   0xFC14  /* posição X inicial (16 bits com sinal)      */
#define LX_R_VPOSSTRT   0xFC16  /* posição Y inicial                          */
#define LX_R_SPRHSIZ    0xFC18  /* escala horizontal 8.8 ($0100 = 1,0)        */
#define LX_R_SPRVSIZ    0xFC1A  /* escala vertical 8.8                        */
#define LX_R_STRETCH    0xFC1C  /* acréscimo de HSIZ por linha (perspectiva)  */
#define LX_R_TILT       0xFC1E  /* acréscimo de HPOS por linha (cisalhamento) */
#define LX_R_SPRDOFF    0xFC20  /* offset p/ próxima linha de dados           */
#define LX_R_SPRVPOS    0xFC22  /* VPOS corrente                              */
#define LX_R_COLLOFF    0xFC24  /* offset do depósito de colisão              */
#define LX_R_VSIZACUM   0xFC26  /* acumulador de tamanho vertical             */
#define LX_R_HSIZOFF    0xFC28  /* offset de tamanho horizontal               */
#define LX_R_VSIZOFF    0xFC2A  /* offset de tamanho vertical                 */
#define LX_R_SCBADR     0xFC2C  /* SCB corrente                               */
#define LX_R_PROCADR    0xFC2E  /* endereço de dados em processamento         */

/* ---- Coprocessador matemático (multiplicação/divisão em hardware) --------- */
#define LX_R_MATHD      0xFC52  /* [VERIFY] grupo ABCD: A=FC55 B=FC54 C=FC53 D=FC52 */
#define LX_R_MATHC      0xFC53
#define LX_R_MATHB      0xFC54
#define LX_R_MATHA      0xFC55
#define LX_R_MATHP      0xFC56  /* divisor (alto)                              */
#define LX_R_MATHN      0xFC57
#define LX_R_MATHH      0xFC60  /* [VERIFY] grupo EFGH                         */
#define LX_R_MATHG      0xFC61
#define LX_R_MATHF      0xFC62
#define LX_R_MATHE      0xFC63
#define LX_R_MATHM      0xFC6C  /* [VERIFY] grupo JKLM (resto/acumulador)      */
#define LX_R_MATHL      0xFC6D
#define LX_R_MATHK      0xFC6E
#define LX_R_MATHJ      0xFC6F

/* ---- Controle e status ---------------------------------------------------------- */
#define LX_R_SPRCTL0    0xFC80
#define LX_R_SPRCTL1    0xFC81
#define LX_R_SPRCOLL    0xFC82
#define LX_R_SPRINIT    0xFC83
#define LX_R_SUZYHREV   0xFC88
#define LX_R_SUZYSREV   0xFC89
#define LX_R_SUZYBUSEN  0xFC90
#define LX_R_SPRGO      0xFC91  /* escrita com bit0=1 dispara o motor de sprites */
#define LX_R_SPRSYS     0xFC92  /* status (busy, math, colisão...) / controle     */
#define LX_R_JOYSTICK   0xFCB0
#define LX_R_SWITCHES   0xFCB1
#define LX_R_RCART0     0xFCB2  /* leitura serial do cartucho, banco 0 */
#define LX_R_RCART1     0xFCB3
#define LX_R_LEDS       0xFCC0
#define LX_R_PARSTATUS  0xFCC2
#define LX_R_PARDATA    0xFCC3
#define LX_R_HOWIE      0xFCC4

/* ---- SPRCTL0 [VERIFY bit a bit] ----------------------------------------------------
 *  b7-b6 bits por pixel-1 (00=1bpp 01=2bpp 10=3bpp 11=4bpp)
 *  b5    HFLIP   b4 VFLIP   b3 (reservado)   b2-b0 tipo de sprite              */
#define LX_CTL0_BPP_MASK    0xC0
#define LX_CTL0_BPP_SHIFT   6
#define LX_CTL0_HFLIP       0x20
#define LX_CTL0_VFLIP       0x10
#define LX_CTL0_TYPE_MASK   0x07

/* Tipos de sprite (SPRCTL0 b2-b0) [VERIFY] */
#define LX_SPR_BACKGROUND     0  /* opaco, com colisão                         */
#define LX_SPR_BACKGND_NOCOL  1  /* opaco, sem colisão                         */
#define LX_SPR_BSHADOW        2  /* opaco + sombra (pen 0xE)                   */
#define LX_SPR_BOUNDARY       3  /* pen 0 transparente; colisão de fronteira   */
#define LX_SPR_NORMAL         4  /* pen 0 transparente; com colisão            */
#define LX_SPR_NONCOLL        5  /* pen 0 transparente; sem colisão            */
#define LX_SPR_XOR            6  /* XOR com o fundo                            */
#define LX_SPR_SHADOW         7  /* sombra (pen 0xE) sobre o fundo             */

/* ---- SPRCTL1 [VERIFY bit a bit] -----------------------------------------------------
 *  b7 LITERAL (dados sem RLE)     b5-b4 RELOAD_DEPTH (0 nada, 1 tamanho,
 *  2 tamanho+stretch, 3 tamanho+stretch+tilt)   b3 REUSE_PALETTE (não há 8 bytes
 *  de paleta no SCB)   b2 SKIP   b1 START_UP   b0 START_LEFT                  */
#define LX_CTL1_LITERAL        0x80
#define LX_CTL1_DEPTH_MASK     0x30
#define LX_CTL1_DEPTH_SHIFT    4
#define LX_CTL1_REUSE_PALETTE  0x08
#define LX_CTL1_SKIP           0x04
#define LX_CTL1_START_UP       0x02
#define LX_CTL1_START_LEFT     0x01

#endif /* LX_SUZY_REGS_H */
