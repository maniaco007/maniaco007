# games/ — perfis por jogo

Um diretório por jogo com `manifest.toml` (veja `_template/`). **Não commitar ROMs**
(`*.lnx`, `*.lyx`, imagens de boot) — `.gitignore` os exclui; cada usuário fornece as suas.
O manifest é amarrado à ROM pelo SHA-256 (`[game] cart_sha256`).
