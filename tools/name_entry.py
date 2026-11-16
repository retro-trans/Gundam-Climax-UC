"""English keyboard for the name-entry screen (2nd-generation character name, Progress mode).

The screen is a scene script (nameentry.bin; a second copy sits in nameentry.pack.fpk). Its keyboard
is a 5 x 17 table at 0x46AD4: each row is u32 17 followed by 17 u32 Shift-JIS codes (0xFFFFFFFF = no
key). Columns 0-9 are the kana grid (image nameentry_kana01), 10-14 small kana and marks, 15-16 the
commands D (delete), B (backspace), arrows, space, X (back) and O (OK) (image nameentry_kana02).

The script inserts a key with the generic text command 0x307400, which writes one byte for codes
below 0x100 (ASCII) and two for Shift-JIS, so letters go in as ASCII and are drawn with the
variable-width font. Only the codes change: every key that existed still exists in the same place
and the empty cells stay empty, so cursor movement is unchanged. The voiced-mark keys (0x814A/B) are
replaced, so the kana voicing code is never reached. Space becomes ASCII 0x20.

Real-hardware note: data-only change of a scene file, same size.
"""
import struct

TABLE_OFF = 0x46AD4
ROWS, COLS = 5, 17
FILES = ('nameentry.bin', 'nameentry.pack.fpk')
NONE = 0xFFFFFFFF

# new key text per row for columns 0-14 ('' = no key); columns 15-16 (commands) are kept,
# except the space key (row 2), which becomes ASCII space
LAYOUT = [
    ['A', 'B', 'C', 'D', 'E', 'Z', 'a', 'b', 'c', 'd', 'u', 'v', 'w', 'x', 'y'],
    ['F', 'G', 'H', 'I', 'J', 'e', 'f', 'g', 'h', 'i', 'z', '-', '.', "'", ''],
    ['K', 'L', 'M', 'N', 'O', 'j', '', 'k', '', 'l', '!', '?', '&', ',', ''],
    ['P', 'Q', 'R', 'S', 'T', 'm', 'n', 'o', 'p', 'q', '', '', '', '', ''],
    ['U', 'V', 'W', 'X', 'Y', 'r', 's', 't', '', '', '', '', '', '', ''],
]


def read_table(d):
    rows = []
    for r in range(ROWS):
        p = TABLE_OFF + r * (4 + COLS * 4)
        n = struct.unpack_from('<I', d, p)[0]
        assert n == COLS, (r, n)
        rows.append(list(struct.unpack_from('<%dI' % COLS, d, p + 4)))
    return rows


def new_table(old):
    rows = []
    for r in range(ROWS):
        row = list(old[r])
        for c in range(15):
            key = LAYOUT[r][c]
            if (row[c] == NONE) != (key == ''):
                raise ValueError('row %d col %d: key layout must keep the original empty cells' % (r, c))
            if key:
                row[c] = ord(key)
        if row[15] == 0x8140:                      # space key
            row[15] = row[16] = 0x20
        rows.append(row)
    return rows


def pack(rows):
    out = b''
    for row in rows:
        out += struct.pack('<I', COLS) + struct.pack('<%dI' % COLS, *row)
    return out


def apply(entries, report, game_dir):
    import os
    n = 0
    for name in FILES:
        data = entries.get(name)
        if data is None:
            data = open(os.path.join(game_dir, name), 'rb').read()
        ref = open(os.path.join(game_dir, 'nameentry.bin'), 'rb').read()
        old = pack(read_table(ref))
        new = pack(new_table(read_table(ref)))
        assert len(old) == len(new)
        c = data.count(old)
        if c != 1:
            report.append('NAME ENTRY %s: table found %d times, not patched' % (name, c))
            continue
        entries[name] = data.replace(old, new)
        n += 1
    report.append('NAME ENTRY keyboard: %d files' % n)
    return entries


# key images: (image, list of (x_centre, y_centre, text)) in texture pixels
ROW_Y = (10, 35, 62, 88, 116)
COL_X01 = (11, 28, 46, 64, 82, 119, 137, 154, 172, 190)        # nameentry_kana01: columns 0-9
COL_X02 = (12, 29, 47, 66, 83)                                   # nameentry_kana02: columns 10-14


def key_cells():
    k1, k2 = [], []
    for r in range(ROWS):
        for c in range(15):
            t = LAYOUT[r][c]
            if not t:
                continue
            if c < 10:
                k1.append((COL_X01[c], ROW_Y[r], t))
            else:
                k2.append((COL_X02[c - 10], ROW_Y[r], t))
    return k1, k2


if __name__ == '__main__':
    import os
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = open(os.path.join(ROOT, 'work', 'source', 'game', 'nameentry.bin'), 'rb').read()
    for row in new_table(read_table(d)):
        print(' '.join(('%c' % v if v < 0x100 else ('--' if v == NONE else hex(v))) for v in row))
