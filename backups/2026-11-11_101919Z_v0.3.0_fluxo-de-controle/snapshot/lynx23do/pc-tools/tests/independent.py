"""Líderes de bloco calculados por um algoritmo SIMPLES e INDEPENDENTE do lynx2c.

Usa só a tabela do núcleo de referência (derivada do padrão de bits). Serve de oráculo para o CFG:
um líder esquecido pelo tradutor faria o diferencial de programas "concordar" por engano (a referência
para onde o tradutor para), então o gerador de programas EXIGE igualdade com este conjunto.
"""
from lynxtrace.core65c02 import REF_OPS, FLOW_MNEMONICS, _LEN


def independent_leaders(image, org, entries):
    """Líderes calculados por um algoritmo SIMPLES e independente, usando a tabela do núcleo de referência."""
    end = org + len(image)
    seen, leaders, work = set(), set(entries), list(entries)
    while work:
        a = work.pop()
        while org <= a < end and a not in seen:
            seen.add(a)
            mn, mode = REF_OPS[image[a - org]]
            n = _LEN[mode]
            nxt = (a + n) & 0xFFFF
            if mn not in FLOW_MNEMONICS:
                a = nxt
                continue
            if mode == "rel":
                off = image[a - org + 1]
                tgt = (nxt + (off - 256 if off & 0x80 else off)) & 0xFFFF
                targets = [tgt] if mn == "BRA" else [tgt, nxt]
            elif mn == "JMP" and mode == "abs":
                targets = [image[a - org + 1] | image[a - org + 2] << 8]
            elif mn == "JSR":
                targets = [image[a - org + 1] | image[a - org + 2] << 8, nxt]
            else:
                targets = []                                  # JMP indireto, RTS
            for t in targets:
                if org <= t < end:
                    leaders.add(t)
                    work.append(t)
            break
    return leaders
