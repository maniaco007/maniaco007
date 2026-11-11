/*
 * lx_host_main.c — executa um jogo traduzido (lx_game_image + lx_ov0 + lx_program) no PC, sem tela.
 * Uso: lx_host FRAMES DUMP_FRAME SAIDA.ppm [JOYSTICK_HEX]
 *   roda FRAMES quadros; o quadro DUMP_FRAME (a partir de 0) é gravado como PPM; JOYSTICK_HEX alimenta $FCB0.
 */
#include <stdio.h>
#include <stdlib.h>

#include "lynx/lx_machine.h"
#include "lynx/lx_platform.h"

extern const lx_u8 lx_game_image[];
extern const lx_u32 lx_game_image_size, lx_game_load_addr, lx_game_entry;
extern const LxOverlay lx_ov0;
extern lx_u8 lx_host_joystick;
extern const char *lx_host_dump_path;
extern lx_u32 lx_host_dump_frame;

int main(int argc, char **argv)
{
    unsigned long frames, i;
    if (argc < 4) { fprintf(stderr, "uso: %s FRAMES DUMP_FRAME SAIDA.ppm [JOY_HEX]\n", argv[0]); return 2; }
    frames = strtoul(argv[1], 0, 10);
    lx_host_dump_frame = (lx_u32)strtoul(argv[2], 0, 10);
    lx_host_dump_path = argv[3];
    if (argc > 4) lx_host_joystick = (lx_u8)strtoul(argv[4], 0, 16);

    lx_gfx_init();
    if (lx_machine_init(lx_game_image, lx_game_image_size, lx_game_load_addr, &lx_ov0, lx_game_entry)) {
        fprintf(stderr, "imagem não cabe na RAM\n");
        return 2;
    }
    for (i = 0; i < frames; i++) {
        if (lx_machine_run_frame()) {
            printf("PARADO em $%04lX (PC sem tradução)\n", (unsigned long)lx_machine_pc());
            return 3;
        }
        lx_machine_present();
    }
    printf("quadros=%lu sprgo_ignorados=%lu\n", frames, (unsigned long)lx_suzy_min_sprgo_ignored);
    return 0;
}
