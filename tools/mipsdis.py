"""Disassemble SLPS_256.27 (PS2 EE, MIPS R5900 little endian) with capstone.

Usage:
  python mipsdis.py <addr_hex> [count]           disassemble count insns from addr
  python mipsdis.py --find-imm <imm_hex> [op]    list insns using a 16-bit immediate
  python mipsdis.py --callers <addr_hex>         list jal to addr
"""
import os
import struct
import sys

import capstone

ELF = os.path.join(os.path.dirname(__file__), '..', 'work', 'source', 'iso', 'SLPS_256.27')
BASE, FOFF = 0x100000, 0x80


def load(path=ELF):
    d = open(path, 'rb').read()
    return d[FOFF:]


def disasm(img, addr, count):
    md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS64 + capstone.CS_MODE_LITTLE_ENDIAN)
    off = addr - BASE
    out = []
    for i in range(count):
        w = img[off + 4 * i: off + 4 * i + 4]
        ins = list(md.disasm(w, addr + 4 * i))
        if ins:
            out.append('%08X: %08X  %s %s' % (addr + 4 * i, struct.unpack('<I', w)[0], ins[0].mnemonic, ins[0].op_str))
        else:
            out.append('%08X: %08X  ???' % (addr + 4 * i, struct.unpack('<I', w)[0]))
    return out


def words(img):
    n = len(img) // 4
    return struct.unpack('<%dI' % n, img[:n * 4])


if __name__ == '__main__':
    a = sys.argv[1:]
    img = load()
    if a[0] == '--find-imm':
        imm = int(a[1], 16)
        for i, w in enumerate(words(img)[:0x270000 // 4]):
            if (w & 0xFFFF) == imm and (w >> 26) not in (0,):
                print('\n'.join(disasm(img, BASE + 4 * i, 1)))
    elif a[0] == '--callers':
        t = int(a[1], 16)
        j = (3 << 26) | ((t >> 2) & 0x3FFFFFF)
        for i, w in enumerate(words(img)):
            if w == j:
                print('%08X' % (BASE + 4 * i))
    else:
        print('\n'.join(disasm(img, int(a[0], 16), int(a[1]) if len(a) > 1 else 40)))
