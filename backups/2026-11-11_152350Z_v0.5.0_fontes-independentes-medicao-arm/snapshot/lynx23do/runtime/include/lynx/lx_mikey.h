/*
 * lx_mikey.h — HLE do Mikey ($FD00-$FDFF): timers, paleta, DMA de vídeo, UART, áudio.
 * Nesta versão só o contrato mínimo de acesso (o código gerado já chama estas
 * funções para operandos absolutos em $FD00-$FDFF). Implementação: fase posterior.
 */
#ifndef LX_MIKEY_H
#define LX_MIKEY_H

#include "lx_types.h"
#include "lx_config.h"

lx_u8 lx_mikey_read (lx_u32 addr);              /* addr em $FD00-$FDFF */
void  lx_mikey_write(lx_u32 addr, lx_u8 val);

#endif /* LX_MIKEY_H */
