# spritecook — sprites do Suzy → dados de Cel do 3DO

Converte dados de linha do Suzy (RLE de 1–4 bpp, *offset* por linha, tipo/pens do SCB)
em Cel **"packed"** do 3DO (também RLE por linha ⇒ sem inflar a RAM) e gera o índice
`cart_offset → cel` (`lxdata.idx`) usado por `lx_suzy_sprite_source()`.
Entradas: SCBs/`SPRDLINE` do `trace.bin` + `DATA_SPRITE` do `classmap.bin`.
Ver `docs/03-hle-suzy.md` §3. Sprites gerados em RAM em tempo de execução usam o
caminho de *runtime cache* do HLE.
