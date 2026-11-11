# pack3do — empacotamento para o SDK/disco do 3DO

Gera, em `build/<jogo>/3do/`: `Makefile` do SDK (armcc/armlink + conversão para
executável 3DO), a árvore de arquivos do disco (executável, `lxdata.bin`, `lxdata.idx`)
e a imagem `.iso`. Os nomes e flags exatos das ferramentas do SDK devem ser
conferidos na documentação oficial (indisponível neste ambiente).
