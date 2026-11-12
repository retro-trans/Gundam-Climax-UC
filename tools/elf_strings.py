"""Extract referenced Shift-JIS strings from SLPS_256.27.

A string counts when it is null-terminated, holds at least one Japanese character,
and its address is referenced either by a 32-bit pointer in the image or by a
MIPS lui/addiu (or lui/ori) pair.

Usage: python elf_strings.py <elf> <out.json>
"""
import json
import re
import struct
import sys

sys.path.insert(0, __file__.rsplit('\\', 1)[0].rsplit('/', 1)[0])
from sjis_scan import scan  # noqa: E402

BASE = 0x100000
FOFF = 0x80


def code_refs(img):
    """Return {addr: [insn offsets]} for lui/addiu|ori|lw|sw... address formation."""
    refs = {}
    n = len(img) // 4
    words = struct.unpack('<%dI' % n, img[:n * 4])
    last_lui = {}
    for i, w in enumerate(words):
        op = w >> 26
        rs = (w >> 21) & 31
        rt = (w >> 16) & 31
        imm = w & 0xFFFF
        if op == 0x0F:  # lui
            last_lui[rt] = (i, imm)
            continue
        if op in (0x09, 0x0D, 0x23, 0x20, 0x24, 0x21, 0x25, 0x2B, 0x28, 0x29, 0x37, 0x3F):
            if rs in last_lui and i - last_lui[rs][0] < 24:
                hi = last_lui[rs][1]
                if op == 0x0D:
                    a = (hi << 16) | imm
                else:
                    a = ((hi << 16) + (imm - 0x10000 if imm & 0x8000 else imm)) & 0xFFFFFFFF
                refs.setdefault(a, []).append(i * 4)
        # crude: branch/jump ends basic block
        if op in (2, 3):
            last_lui = {}
    return refs


def main():
    elf, out = sys.argv[1:3]
    data = open(elf, 'rb').read()
    img = data[FOFF:]
    crefs = code_refs(img)
    n = len(img) // 4
    words = struct.unpack('<%dI' % n, img[:n * 4])
    prefs = {}
    for i, w in enumerate(words):
        if BASE <= w < BASE + len(img):
            prefs.setdefault(w, []).append(i * 4)
    res = []
    for off, r in scan(img, 1):
        if off > 0 and img[off - 1] != 0:
            continue
        end = off + len(r)
        if end < len(img) and img[end] != 0:
            continue
        t = r.decode('cp932', 'replace')
        if not re.search('[ぁ-ヿ一-鿿！-～]', t):
            continue
        a = BASE + off
        cr = crefs.get(a, [])
        pr = prefs.get(a, [])
        if not cr and not pr:
            continue
        res.append({'addr': '%08X' % a, 'fileoff': '%X' % (off + FOFF), 'len': len(r),
                    'code_refs': ['%08X' % (BASE + x) for x in cr[:8]],
                    'ptr_refs': ['%08X' % (BASE + x) for x in pr[:8]],
                    'jp': t})
    json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('strings', len(res), 'chars', sum(len(x['jp']) for x in res))


if __name__ == '__main__':
    main()
