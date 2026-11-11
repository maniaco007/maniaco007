# platform/host — backend de PC

Implementa `lx_platform.h` com rasterizador de software (e SDL opcional) para executar
o **mesmo código gerado** no PC e compará-lo, quadro a quadro, com o `lynxtrace`.
É também o oráculo de aparência do HLE (`LX_MAP_NATIVE/APPROX/FALLBACK_SOFT`).
