/*
 * lx_main_3do.c — programa principal no 3DO: executa um jogo traduzido (lx_game_image + lx_ov0 + lx_program,
 * gerados por `lynx2c build`) quadro a quadro. O laço é o mesmo de lx_host_main.c.
 */
#include "types.h"
#include "stdio.h"

#include "lynx/lx_machine.h"
#include "lynx/lx_platform.h"

extern const lx_u8 lx_game_image[];
extern const lx_u32 lx_game_image_size, lx_game_load_addr, lx_game_entry;
extern const LxOverlay lx_ov0;

int main(int argc, char *argv[])
{
    (void)argc; (void)argv;
    printf("lynx23do\n");

    if (lx_gfx_init() < 0) {
        printf("falha ao iniciar o video\n");
        return 1;
    }
    if (lx_machine_init(lx_game_image, lx_game_image_size, lx_game_load_addr, &lx_ov0, lx_game_entry)) {
        printf("a imagem nao cabe na RAM do Lynx\n");
        return 1;
    }
    for (;;) {
        if (lx_machine_run_frame()) {
            printf("PARADO em $%04X: PC sem traducao (acrescente como semente no lynx2c)\n", (unsigned)lx_machine_pc());
            break;
        }
        lx_machine_present();
    }
    return 0;
}
