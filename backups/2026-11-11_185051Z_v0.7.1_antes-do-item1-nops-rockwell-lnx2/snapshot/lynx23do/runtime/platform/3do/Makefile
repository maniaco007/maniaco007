# Makefile do backend 3DO — constrói LaunchMe e a imagem de disco para o ODE.
#
# Requisitos NO SEU PC: o devkit (trapexit/3do-devkit) ativado (`source activate-env` ou activate-env.bat), com
# armcc, armlink, modbin, MakeBanner, 3doiso e 3DOEncrypt no PATH, e Python 3 (tradutor).
# Baseado no Makefile do XProger/nes-3do (BSD-2-Clause; ver NOTICE.md).
#
# Uso:
#   make DEVKIT=/caminho/3do-devkit            # demo_bars -> _build/CD + lynx23do.iso
#   make DEVKIT=... GAME_O=meu_jogo.o NAME=meu # outro homebrew BS93
#
# ESTADO: NÃO testado com o armcc nem em hardware (o ambiente de desenvolvimento não pôde executar o compilador).
# Os alvos `game` e `host-check` rodam em qualquer PC e valem como verificação prévia.

DEVKIT      ?= $(HOME)/3do-devkit
ROOT        := $(abspath ../../..)
NAME        ?= demo
GAME_O      ?= _build/demo.o
OUT         := _build
FILESYSTEM  := $(OUT)/CD
EXENAME     := $(FILESYSTEM)/LaunchMe
ISONAME     := lynx23do.iso
STACKSIZE   ?= 8192

SDK         := $(DEVKIT)
CC          := armcc
LD          := armlink
MODBIN      := modbin
3DOISO      := 3doiso
3DOENCRYPT  := 3DOEncrypt

OPT         ?= -O2
CFLAGS      := $(OPT) -bi -za1 -zas1 -wn -ff -fa -d __3DO__=1 -d LX_TARGET_3DO=1 -cpu ARM6
INCPATH     := -I $(SDK)/include/3do -I $(ROOT)/runtime/include
LIBPATH     := $(SDK)/lib/3do
LDFLAGS     := -aif -reloc -ro-base 0 -libpath $(LIBPATH) -nodebug -remove -info Sizes
STARTUP     := $(LIBPATH)/cstartup.o
LIBS        := $(LIBPATH)/clib.lib $(LIBPATH)/swi.lib $(LIBPATH)/lib3do.lib $(LIBPATH)/operamath.lib \
               $(LIBPATH)/audio.lib $(LIBPATH)/music.lib $(LIBPATH)/filesystem.lib $(LIBPATH)/graphics.lib \
               $(LIBPATH)/input.lib

RUNTIME_C   := lx_mem lx_dispatch lx_overlay lx_alu lx_video lx_mikey lx_suzy_min lx_machine
SRC_C       := $(addprefix $(ROOT)/runtime/src/,$(addsuffix .c,$(RUNTIME_C))) \
               lx_platform_3do.c lx_main_3do.c $(OUT)/$(NAME)_gen.c $(OUT)/$(NAME)_image.c
OBJ         := $(addprefix $(OUT)/,$(notdir $(SRC_C:.c=.o)))

.PHONY: all game launchme iso host-check clean
all: iso

# 1) tradução no PC (lynx2c): gera $(NAME)_gen.c e $(NAME)_image.c
game: $(OUT)/$(NAME)_gen.c
$(OUT)/$(NAME)_gen.c: $(GAME_O)
	PYTHONPATH=$(ROOT)/pc-tools/lynx2c python3 -m lynx2c build --file $(GAME_O) --name $(NAME) --out-dir $(OUT)
$(OUT)/demo.o:
	mkdir -p $(OUT)
	python3 $(ROOT)/games/demo_bars/demo.py $(OUT)/demo.o

# 2) compilação com o armcc do SDK
$(OUT)/%.o: %.c
	@mkdir -p $(OUT)
	$(CC) $(INCPATH) $(CFLAGS) -c $< -o $@
$(OUT)/%.o: $(ROOT)/runtime/src/%.c
	@mkdir -p $(OUT)
	$(CC) $(INCPATH) $(CFLAGS) -c $< -o $@
$(OUT)/%.o: $(OUT)/%.c
	@mkdir -p $(OUT)
	$(CC) $(INCPATH) $(CFLAGS) -c $< -o $@

# 3) LaunchMe + disco. O esqueleto do disco (System/, rom_tags, signatures) vem do `takeme/` do SEU devkit.
launchme: $(OBJ)
	mkdir -p $(FILESYSTEM)
	cp -r $(SDK)/takeme/. $(FILESYSTEM)/
	$(LD) -dupok -o $(EXENAME) $(LDFLAGS) $(STARTUP) $(OBJ) $(LIBS)
	$(MODBIN) --stack=$(STACKSIZE) $(EXENAME) $(EXENAME)

iso: launchme
	$(3DOISO) -in $(FILESYSTEM) -out $(ISONAME)
	$(3DOENCRYPT) genromtags $(ISONAME)
	@echo "Gerado: $(ISONAME)  (copie para o cartão/USB do ODE)"

# verificação prévia no PC (gcc, sem o SDK): gera o jogo e roda no backend de host
host-check: $(OUT)/$(NAME)_gen.c
	gcc -std=c89 -pedantic -Wall -Wextra -Werror -I $(ROOT)/runtime/include $(OUT)/$(NAME)_gen.c $(OUT)/$(NAME)_image.c \
	    $(addprefix $(ROOT)/runtime/src/,$(addsuffix .c,$(RUNTIME_C))) \
	    $(ROOT)/runtime/platform/host/lx_platform_host.c $(ROOT)/runtime/platform/host/lx_host_main.c -o $(OUT)/host_$(NAME)
	$(OUT)/host_$(NAME) 8 6 $(OUT)/$(NAME).ppm 00

clean:
	rm -rf $(OUT) $(ISONAME)
