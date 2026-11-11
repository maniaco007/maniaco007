"""Estágio A — ingest: reconhece o formato do arquivo e produz o que o resto do pipeline precisa.

Formatos (confirmados contra o emulador Handy, como DADO de referência):
  .lnx  cabeçalho de 64 bytes: 'LYNX' | u16 page_size_bank0 | u16 page_size_bank1 | u16 version(=1) | cartname[32] |
        manufname[16] | rotation | audin | eeprom | spare[3]. Campos de 16 bits são LITTLE-endian no arquivo.
        Tamanho do banco = page_size * 256 bytes (0x100 -> 64 KB, 0x200 -> 128 KB, 0x400 -> 256 KB, 0x800 -> 512 KB).
        rotation: 0 nenhuma, 1 esquerda, 2 direita (outro valor -> nenhuma). audin = bit 0 de 'audin'.
        ATENÇÃO: jogos comerciais NÃO têm código executável conhecido aqui: o 1º bloco é cifrado e só a ROM de boot do
        Lynx (que o usuário fornece ao lynxtrace) o decifra e carrega. O ingest só descreve o cartucho.
  LNX2  cabeçalho de 64 bytes (formato da comunidade; lido como DADO de referência do Gearlynx): 'LNX2' | bank[4] |
        u16 version(=1, little-endian) | name[32] | manufacturer[16] | rotation | flags | eeprom | reserved | custom | sd_api.
        bank[i] (ordem: banco0, banco0-A, banco1, banco1-A): bits 7..6 = tipo (0 não usado, 1 RAM persistente, 2 RAM, 3 ROM);
        tamanho = (16 << (b & 7)) * (2 << ((b >> 3) & 7)) bytes. flags bit 0 = console Lynx II (liga os opcodes Rockwell).
  BS93  homebrew carregável pela ROM de boot: 10 bytes = 0x80 0x08 (BRA +8: o cabeçalho é executável!) | u16 BIG-endian
        load_address (endereço do 1º byte APÓS o cabeçalho) | u16 BIG-endian size | 'BS93'. O arquivo inteiro vai para
        load_address-10 e o PC inicial é load_address-10 (o BRA pula os 8 bytes restantes do cabeçalho).
  raw   imagem plana (testes/Dormann): o chamador informa org e entrada.
"""
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional

LNX_HEADER_SIZE = 64
BS93_HEADER_SIZE = 10
_BANK_PAGE_SIZES = {0x000: 0, 0x100: 64 * 1024, 0x200: 128 * 1024, 0x400: 256 * 1024, 0x800: 512 * 1024}
ROTATIONS = {0: "nenhuma", 1: "esquerda", 2: "direita"}


class IngestError(Exception):
    pass


@dataclass
class CartInfo:
    kind: str                         # 'lnx' | 'bs93' | 'raw'
    sha256: str
    size: int                         # bytes do arquivo
    name: str = ""
    manufacturer: str = ""
    version: int = 0
    rotation: str = "nenhuma"
    audin: bool = False
    eeprom: int = 0
    bank0_bytes: int = 0
    bank1_bytes: int = 0
    data: bytes = b""                 # lnx: bancos (sem cabeçalho); bs93: arquivo inteiro; raw: arquivo
    load_addr: Optional[int] = None   # bs93/raw: onde a imagem vai na RAM do Lynx (inclui o cabeçalho BS93)
    entry: Optional[int] = None       # bs93/raw: PC inicial conhecido
    executable_known: bool = False    # True quando o código é conhecido SEM executar a ROM de boot
    cpu: str = "lynx1"                # modelo de CPU a usar na decodificação: lynx1 (padrão) | lynx2 (LNX2 flags bit 0)
    lnx2_banks: List[tuple] = field(default_factory=list)   # [(tipo, bytes)] por banco 0,0A,1,1A (só LNX2)
    warnings: List[str] = field(default_factory=list)


def _cstr(b: bytes) -> str:
    return b.split(b"\0", 1)[0].decode("latin-1").strip()


def ingest(data: bytes, org: Optional[int] = None, entry: Optional[int] = None) -> CartInfo:
    sha = hashlib.sha256(data).hexdigest()
    if len(data) >= BS93_HEADER_SIZE and data[6:10] == b"BS93":
        return _bs93(data, sha)
    if len(data) >= LNX_HEADER_SIZE and data[0:4] == b"LYNX":
        return _lnx(data, sha)
    if len(data) >= LNX_HEADER_SIZE and data[0:4] == b"LNX2":
        return _lnx2(data, sha)
    if org is None:
        raise IngestError("formato desconhecido (nem .lnx nem BS93): informe --org para tratar como imagem plana")
    info = CartInfo("raw", sha, len(data), data=data, load_addr=org, entry=org if entry is None else entry,
                    executable_known=True)
    if org + len(data) > 0x10000:
        raise IngestError("imagem plana ultrapassa o espaço de 64 KB")
    return info


def _lnx(data: bytes, sha: str) -> CartInfo:
    p0 = data[4] | (data[5] << 8)
    p1 = data[6] | (data[7] << 8)
    version = data[8] | (data[9] << 8)
    info = CartInfo("lnx", sha, len(data), name=_cstr(data[10:42]), manufacturer=_cstr(data[42:58]), version=version)
    rot = data[58]
    info.rotation = ROTATIONS.get(rot, "nenhuma")
    if rot not in ROTATIONS:
        info.warnings.append("rotação %d inválida: tratada como nenhuma (igual ao Handy)" % rot)
    info.audin = bool(data[59] & 1)
    info.eeprom = data[60]
    if version != 1:
        info.warnings.append("versão de cabeçalho %d (esperado 1)" % version)
    for idx, p in ((0, p0), (1, p1)):
        if p not in _BANK_PAGE_SIZES:
            raise IngestError("tamanho de página inválido para o banco %d: 0x%X (esperado 0, 0x100, 0x200, 0x400 ou 0x800)" % (idx, p))
    info.bank0_bytes, info.bank1_bytes = _BANK_PAGE_SIZES[p0], _BANK_PAGE_SIZES[p1]
    info.data = data[LNX_HEADER_SIZE:]
    want = info.bank0_bytes + info.bank1_bytes
    if len(info.data) != want:
        info.warnings.append("dados (%d bytes) != bancos declarados (%d bytes)" % (len(info.data), want))
    return info


BANK_TYPES = {0: "não usado", 1: "RAM persistente", 2: "RAM", 3: "ROM"}


def lnx2_bank_size(desc: int) -> int:
    """Tamanho em bytes de um descritor de banco LNX2 (0 se o tipo é 'não usado')."""
    if desc >> 6 == 0:
        return 0
    return (16 << (desc & 7)) * (2 << ((desc >> 3) & 7))


def _lnx2(data: bytes, sha: str) -> CartInfo:
    banks = data[4:8]
    version = data[8] | (data[9] << 8)
    info = CartInfo("lnx", sha, len(data), name=_cstr(data[10:42]), manufacturer=_cstr(data[42:58]), version=version)
    info.rotation = ROTATIONS.get(data[58], "nenhuma")
    if data[58] not in ROTATIONS:
        info.warnings.append("rotação %d inválida: tratada como nenhuma" % data[58])
    flags = data[59]
    info.eeprom = data[60]
    info.audin = (banks[1] >> 6) != 0 or (banks[3] >> 6) != 0            # bancos "A" presentes => AUDIN usado
    if version != 1:
        info.warnings.append("versão de cabeçalho LNX2 %d (esperado 1)" % version)
    if flags & 1:
        info.cpu = "lynx2"
    if flags & ~1:
        info.warnings.append("flags LNX2 com bits desconhecidos: 0x%02X" % (flags & ~1))
    sizes = [lnx2_bank_size(b) for b in banks]
    info.lnx2_banks = [(b >> 6, s) for b, s in zip(banks, sizes)]
    info.bank0_bytes, info.bank1_bytes = sizes[0], sizes[2]
    info.data = data[LNX_HEADER_SIZE:]
    want = sum(sizes)
    if len(info.data) != want:
        info.warnings.append("dados (%d bytes) != bancos declarados (%d bytes)" % (len(info.data), want))
    for i, b in enumerate(banks):
        if (b >> 6) in (1, 2):
            info.warnings.append("banco %d é %s: o cartucho tem RAM/NVRAM própria (não suportado ainda)" % (i, BANK_TYPES[b >> 6]))
    return info


def _bs93(data: bytes, sha: str) -> CartInfo:
    if data[0] != 0x80 or data[1] != 0x08:
        raise IngestError("BS93 sem o BRA +8 inicial (80 08): cabeçalho inesperado")
    load = (data[2] << 8) | data[3]
    size = (data[4] << 8) | data[5]
    if load < BS93_HEADER_SIZE:
        raise IngestError("BS93: load_address $%04X menor que o cabeçalho" % load)
    base = load - BS93_HEADER_SIZE
    info = CartInfo("bs93", sha, len(data), data=data, load_addr=base, entry=base, executable_known=True)
    if size > len(data):
        info.warnings.append("size do cabeçalho (%d) maior que o arquivo (%d): usando o arquivo" % (size, len(data)))
    elif size < len(data):
        info.warnings.append("size do cabeçalho (%d) menor que o arquivo (%d): bytes finais ignorados (igual ao Handy)" % (size, len(data)))
        info.data = data[:size]
    if base + len(info.data) > 0x10000:
        raise IngestError("BS93 ultrapassa o espaço de 64 KB")
    return info


def build_lnx(bank0: bytes, bank1: bytes = b"", name: str = "TESTE", manufacturer: str = "LYNX23DO",
              rotation: int = 0, audin: int = 0, eeprom: int = 0) -> bytes:
    """Monta um .lnx válido (para testes)."""
    def page(n):
        for p, sz in _BANK_PAGE_SIZES.items():
            if sz == n:
                return p
        raise ValueError("tamanho de banco inválido: %d" % n)
    hdr = bytearray(b"LYNX")
    hdr += bytes([page(len(bank0)) & 0xFF, page(len(bank0)) >> 8, page(len(bank1)) & 0xFF, page(len(bank1)) >> 8, 1, 0])
    hdr += name.encode("latin-1")[:32].ljust(32, b"\0") + manufacturer.encode("latin-1")[:16].ljust(16, b"\0")
    hdr += bytes([rotation, audin, eeprom, 0, 0, 0])
    assert len(hdr) == LNX_HEADER_SIZE
    return bytes(hdr) + bank0 + bank1


def build_lnx2(banks, name: str = "TESTE", manufacturer: str = "LYNX23DO", rotation: int = 0, flags: int = 0,
               eeprom: int = 0) -> bytes:
    """Monta um LNX2 (para testes). banks = até 4 itens [(tipo, bytes)] na ordem banco0, 0A, 1, 1A (tipo 3 = ROM)."""
    desc, payload = [], b""
    for tipo, blob in list(banks) + [(0, b"")] * (4 - len(banks)):
        if tipo == 0:
            desc.append(0)
            continue
        for bsz in range(8):
            for bcnt in range(8):
                if (16 << bsz) * (2 << bcnt) == len(blob):
                    desc.append(tipo << 6 | bcnt << 3 | bsz)
                    break
            else:
                continue
            break
        else:
            raise ValueError("tamanho de banco LNX2 inválido: %d" % len(blob))
        payload += blob
    hdr = bytearray(b"LNX2") + bytes(desc) + bytes([1, 0])
    hdr += name.encode("latin-1")[:32].ljust(32, b"\0") + manufacturer.encode("latin-1")[:16].ljust(16, b"\0")
    hdr += bytes([rotation, flags, eeprom, 0, 0, 0])
    assert len(hdr) == LNX_HEADER_SIZE
    return bytes(hdr) + payload


def build_bs93(code: bytes, load_addr: int) -> bytes:
    """Monta um BS93 (para testes): load_addr = endereço do 1º byte de 'code' (após o cabeçalho de 10 bytes)."""
    total = BS93_HEADER_SIZE + len(code)
    return bytes([0x80, 0x08, load_addr >> 8, load_addr & 0xFF, total >> 8, total & 0xFF]) + b"BS93" + code
