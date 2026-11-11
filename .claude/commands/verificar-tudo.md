---
description: Roda toda a verificação do projeto e mostra as contagens reais (unitários, diferencial, Dormann, headers, backups)
---
Execute, nesta ordem, **você mesmo**, e mostre a saída resumida de cada um (contagens reais, não de memória):

1. `export PYTHONPATH=$PWD/lynx23do/pc-tools/lynx2c:$PWD/lynx23do/pc-tools/lynxtrace:$PWD/lynx23do/pc-tools/tests`
2. `python3 -m unittest discover -s lynx23do/pc-tools/tests -p 'test_*.py'`  (esperado hoje: 149 OK)
3. `lynx23do/pc-tools/tests/run_diff.sh`  (esperado: 0 falhas em -O0 e -O2; ~80 s)
4. `lynx23do/pc-tools/tests/functional/run_dormann.sh`  (esperado: as duas suítes PASSAM; precisa de rede)
5. `lynx23do/scripts/check_headers.sh`
6. `lynx23do/scripts/check_3do_build.sh`  (se o devkit estiver acessível, passe `DEVKIT=<caminho>`)
7. `scripts/check_backups_immutable.sh` e `scripts/check_claude_config.sh`

Termine com uma tabela: verificação → resultado → divergência em relação ao esperado. Se algo falhar, **não corrija agora**: reporte a primeira falha com o comando que a reproduz.
