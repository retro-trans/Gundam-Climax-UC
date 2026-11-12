"""English save title in the PS2 icon.sys of the game's save package (saga_mc.fpk).

The PS2 memory-card browser draws the title from icon.sys (+0xC0, 68 bytes, Shift-JIS) with the
system font, breaking the line at the byte offset stored at +6. Full-width characters are used, as
in the original (the browser font is full-width). Only saves created with the patched game get the
new title; existing saves keep theirs.

Real-hardware note: icon.sys layout is the standard PS2 format; only the title bytes and the
line-break offset change (both within the documented fields).
"""
import glob
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPK = os.path.join(ROOT, 'work', 'source', 'fpk')
GAME = os.path.join(ROOT, 'work', 'source', 'game')
SRC = 'saga_mc.fpk_/icon.sys'
LINE1 = 'ＭＯＢＩＬＥ　ＳＵＩＴ　ＧＵＮＤＡＭ'
LINE2 = 'ＣＬＩＭＡＸ　Ｕ．Ｃ．'


def new_icon_sys():
    d = bytearray(open(os.path.join(FPK, SRC), 'rb').read())
    assert d[:4] == b'PS2D'
    t1, t2 = LINE1.encode('cp932'), LINE2.encode('cp932')
    title = t1 + t2
    assert len(title) < 68, len(title)
    d[0xC0:0xC0 + 68] = title + b'\0' * (68 - len(title))
    d[6:8] = len(t1).to_bytes(2, 'little')
    return bytes(d)


def apply(entries, report):
    old = open(os.path.join(FPK, SRC), 'rb').read()
    new = new_icon_sys()
    n = 0
    tops = set()
    for p in glob.glob(os.path.join(FPK, '**', 'icon.sys'), recursive=True):
        if open(p, 'rb').read() == old:
            tops.add(os.path.relpath(p, FPK).replace(os.sep, '/').split('/')[0][:-1])
    for t in sorted(tops):
        data = entries.get(t)
        if data is None:
            data = open(os.path.join(GAME, t), 'rb').read()
        n += data.count(old)
        entries[t] = data.replace(old, new)
    report.append('SAVE TITLE %d copies in %s' % (n, ', '.join(sorted(tops))))
    return entries
