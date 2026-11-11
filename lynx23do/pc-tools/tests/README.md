# Testes do lado PC

Planejados (docs/02 §9):
1. **Diferencial por instrução** — cada opcode × amostra exaustiva de regs/flags/operandos:
   tradução compilada no host vs. `lynxtrace`.
2. **Suítes funcionais 6502/65C02** conhecidas, rodadas pelo pipeline completo no host.
3. **Jogo inteiro** — hash do estado a cada vblank, host-traduzido vs. referência.
4. **Determinismo** — duas execuções do tradutor produzem bytes idênticos.
