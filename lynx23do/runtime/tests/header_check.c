/*
 * header_check.c — garante que TODOS os headers públicos do runtime compilam
 * isoladamente e juntos em C89 estrito. Não é executado, apenas compilado.
 * Rodar: lynx23do/scripts/check_headers.sh
 */
#include "lynx/lx_types.h"
#include "lynx/lx_config.h"
#include "lynx/lx_mem.h"
#include "lynx/lx_cpu_abi.h"
#include "lynx/lx_overlay.h"
#include "lynx/lx_suzy_regs.h"
#include "lynx/lx_cel.h"
#include "lynx/lx_suzy.h"
#include "lynx/lx_platform.h"

/* verificações de layout que o lynx2c e o backend 3DO assumem */
typedef char chk_dispatch_entry_8[(sizeof(LxDispatchEntry) <= 16) ? 1 : -1];
typedef char chk_ram_64k[(LX_RAM_SIZE == 65536UL) ? 1 : -1];
typedef char chk_fb_bytes[(LX_FB_BYTES == 8160) ? 1 : -1];

/* uso mínimo para expor erros de assinatura/macro */
lx_u32 lx_header_check_unit(LxCpu *cpu)
{
    lx_u32 pc = 0x0200;
    lx_u8  p;
    LX_SCHED_CHECK(cpu, 3, pc);
    lx_wr8(0x0010, 0x42);
    cpu->a = lx_rd8(0x0010);
    p = lx_cpu_pack_p(cpu);
    lx_cpu_unpack_p(cpu, p);
    return LX_PC_RETURN;
}
