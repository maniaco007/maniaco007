/* lx_machine.c — ver lx_machine.h. Agendador MÍNIMO: um quadro a cada LX_CYCLES_PER_FRAME ciclos. */
#include <string.h>

#include "lynx/lx_machine.h"
#include "lynx/lx_mem.h"
#include "lynx/lx_platform.h"
#include "lynx/lx_video.h"

LxCpu lx_cpu;
lx_u32 lx_resume_pc;
static lx_u32 g_pc;
static lx_u32 g_frames;

lx_u32 lx_sched_service(LxCpu *cpu, lx_u32 next_pc)
{
    lx_resume_pc = next_pc;
    cpu->next_event = cpu->cycles + LX_CYCLES_PER_FRAME;
    return LX_PC_YIELD;
}

int lx_machine_init(const lx_u8 *image, lx_u32 image_size, lx_u32 load_addr, const LxOverlay *ov, lx_u32 entry)
{
    if (load_addr + image_size > LX_RAM_SIZE) return 1;
    memset(lx_ram, 0, LX_RAM_SIZE);
    memcpy(&lx_ram[load_addr], image, image_size);
    memset(&lx_cpu, 0, sizeof lx_cpu);
    lx_cpu.s = 0xFF;
    lx_cpu.i = 1;
    lx_video_reset();
    lx_overlay_reset();
    lx_overlay_activate(ov);
    g_pc = entry;
    g_frames = 0;
    return 0;
}

int lx_machine_run_frame(void)
{
    lx_u32 r;
    lx_cpu.next_event = lx_cpu.cycles + LX_CYCLES_PER_FRAME;
    r = lx_run(&lx_cpu, g_pc);
    if (r == LX_PC_YIELD) {
        g_pc = lx_resume_pc;
        g_frames++;
        return 0;
    }
    g_pc = (r <= 0xFFFFUL) ? r : lx_unresolved_pc;
    return 1;
}

void lx_machine_present(void)
{
    lx_u16 plut[LX_PALETTE_SIZE];
    lx_u32 fb = lx_video_dispadr();

    lx_video_plut(plut);
    lx_gfx_set_palette(plut);
    if (lx_video_dma_enabled() && fb + LX_FB_BYTES <= LX_RAM_SIZE)
        lx_gfx_submit_fb_layer(&lx_ram[fb], 0);
    lx_gfx_present(0);
}

lx_u32 lx_machine_frames(void) { return g_frames; }
lx_u32 lx_machine_pc(void)     { return g_pc; }
