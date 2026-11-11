# Créditos e licenças (backend 3DO)

- **XProger/nes-3do** — BSD 2-Clause, © 2024 Timur Gagiev (https://github.com/XProger/nes-3do). A sequência de inicialização e de
  quadro (`OpenGraphicsFolio`, `InitEventUtility`, `CreateBasicDisplay` com 2 buffers, `DrawScreenCels`, `DisplayScreen`,
  `WaitVBL`), os formatos de ponto fixo do CCB (`HDX = 1<<20`, `VDY = 1<<16`, `XPos = x<<16`) e o fluxo
  `armcc → armlink → modbin → 3doiso → 3DOEncrypt genromtags` do Makefile foram aprendidos desse projeto; o código aqui foi
  reescrito, mas a autoria da ideia e do fluxo é dele. Aviso de copyright e licença do original:

  > Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
  > following conditions are met: (1) redistributions of source code must retain the above copyright notice, this list of
  > conditions and the following disclaimer; (2) redistributions in binary form must reproduce the above copyright notice…

- **trapexit/3do-devkit** — compilador Norcroft ARM, headers e bibliotecas do Portfolio 2.5 e ferramentas. **Não** são
  redistribuídos neste repositório: o Makefile os usa a partir do devkit instalado no PC de quem compila. As constantes do CCB
  (`CCB_*`, `PRE0_*`, `PRE1_*`) foram conferidas lendo `include/3do/graphics.h` e `graphics_ccb.h`.
- **Handy** (libretro-handy) — layout dos registradores de paleta/vídeo do Mikey e do JOYSTICK, lidos como dado de referência.
