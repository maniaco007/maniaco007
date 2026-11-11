# platform/3do — backend 3DO

Implementa `lx_platform.h` com o SDK Portfolio: `LxCelDesc` → CCB (pool estático,
`NextPtr`/`LAST`) → `DrawCels()`; superfícies = `BitmapItem` na VRAM; pad; leitura de
arquivos do CD. **Não implementar antes de conferir** os formatos do CCB e as
assinaturas do SDK contra a documentação oficial (itens `[VERIFY]` em `lx_cel.h`).
Fora do escopo da fase de arquitetura: inicialização do Cel Engine.
