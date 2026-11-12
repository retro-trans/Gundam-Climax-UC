"""Find code references to an address in SLPS_256.27 (lui/addiu|ori|lw|sw pairs and data words).

python tools/xref.py <addr_hex> [...]
python tools/xref.py --str "<ascii text>"     find the string, then its references
"""
import struct
import sys

import mipsdis

IMG = mipsdis.load()
BASE = mipsdis.BASE
W = mipsdis.words(IMG)
TEXT_END = 0x32D000


def refs(target):
    out = []
    hi = ((target + 0x8000) >> 16) & 0xFFFF
    lo = target & 0xFFFF
    n = (TEXT_END - BASE) // 4
    for i in range(n):
        w = W[i]
        if w >> 26 == 0xF and (w & 0xFFFF) == hi:          # lui rt, hi
            rt = (w >> 16) & 31
            for j in range(i + 1, min(i + 24, n)):
                x = W[j]
                op = x >> 26
                if op in (9, 0xD, 0x23, 0x2B, 0x20, 0x24, 0x28, 0x37, 0x3F) and ((x >> 21) & 31) == rt \
                        and (x & 0xFFFF) == lo:
                    out.append(BASE + 4 * j)
                    break
    for i, w in enumerate(W):
        if w == target:
            out.append(('data', BASE + 4 * i))
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == '--str':
        s = a[1].encode('latin-1')
        k = IMG.find(s)
        while k >= 0:
            addr = BASE + k
            print('string at %08X' % addr)
            for r in refs(addr):
                print('   ', r if isinstance(r, tuple) else '%08X' % r)
            k = IMG.find(s, k + 1)
    else:
        for t in a:
            print('%s:' % t, ['%08X' % r if not isinstance(r, tuple) else r for r in refs(int(t, 16))])
