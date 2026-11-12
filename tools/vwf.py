"""Variable-width font support for SLPS-25627.

How the game measures text (see docs/vwf.md):
  CUmeStdFont vtable slot 0x38 = GetCharWidth(font, char*) at 0x1981A0.
  Full-width (2-byte SJIS) chars -> *(*(font+0x450)+4) (20 px).
  Single-byte chars -> HalfWidth(font, byte) at 0x197BF0, originally width/2 (10 px)
  for every byte >= 0x20.

Patch: HalfWidth becomes a table lookup:
    andi  v0, a1, 0xff
    lui   v1, hi(TABLE)
    addu  v1, v1, v0
    jr    ra
    lbu   v0, lo(TABLE)(v1)
Single-byte chars are drawn with the font's half-width glyphs (SJIS row 0x85, JIS row 0x29),
left-aligned in the 20 px cell, so a smaller advance packs them tightly.

Usage:
  python vwf.py table <font.ufm> <out.bin> [--json out.json]
  python vwf.py code <table_addr_hex>      print patch words
"""
import json
import struct
import sys

sys.path.insert(0, __file__.rsplit('\\', 1)[0].rsplit('/', 1)[0])
from ufm_tool import UFM, W, H  # noqa: E402

HALFWIDTH_FN = 0x197BF0
HALFWIDTH_FN_SIZE = 0x40   # 0x197BF0..0x197C2F (function + nop padding)
SPACING = 1                # px of gap after the rightmost ink column
SPACE_WIDTH = 5
FIXED = {}                 # per-char overrides, e.g. {ord('i'): 4}


def ascii_to_sjis(b):
    """Single-byte ASCII: the game looks it up as JIS 0x2900|b (ufm_tool.UFM.index handles it)."""
    return b


def glyph_width(f, code):
    g = f.index(code)
    if g is None:
        return None
    px = f.get_pixels(g)
    right = -1
    left = W
    for y in range(H):
        for x in range(W):
            if px[y * W + x]:
                right = max(right, x)
                left = min(left, x)
    if right < 0:
        return 0
    return right + 1 + SPACING


def left_align_halfwidth(f):
    """Shift every half-width ASCII glyph so its ink starts at column 0. Returns UFM."""
    for b in range(0x21, 0x7F):
        g = f.index(ascii_to_sjis(b))
        if g is None:
            continue
        px = f.get_pixels(g)
        cols = [x for x in range(W) if any(px[y * W + x] for y in range(H))]
        if not cols or cols[0] == 0:
            continue
        s = cols[0]
        new = [0] * (W * H)
        for y in range(H):
            for x in range(W - s):
                new[y * W + x] = px[y * W + x + s]
        f.set_pixels(g, new)
    return f


BOLD = False  # 1 px horizontal emboldening of the ASCII glyphs (used in 0.1.1; reverted in 0.1.2 by request)


def fix_l_glyph(f):
    """The game's 'l' is a bare 1 px stem with no anti-aliasing column, unlike 'i', 'I', '1'. At 1x it
    reads as a hairline and gets a 2 px advance. Redraw it like 'i': grey column + full-ink stem."""
    g = f.index(ascii_to_sjis(ord('l')))
    if g is None:
        return f
    px = f.get_pixels(g)
    rows = [y for y in range(H) if any(px[y * W + x] for x in range(W))]
    new = [0] * (W * H)
    for y in rows:
        new[y * W + 0] = 1
        new[y * W + 1] = 2
    f.set_pixels(g, new)
    return f


J_HOOK = 2   # px the hook of 'j' may reach left of its stem (original: 4)


def fix_j_hook(f):
    """Shorten the hook of 'j' to J_HOOK px left of the stem. With left-aligned glyphs the original
    4 px hook leaves a visible gap after the previous letter ("Ob jectives"). The stem is the first
    column with more than 2 ink pixels; columns further left than J_HOOK are dropped."""
    g = f.index(ascii_to_sjis(ord('j')))
    if g is None:
        return f
    px = f.get_pixels(g)
    stem = next((x for x in range(W) if sum(1 for y in range(H) if px[y * W + x]) > 2), 0)
    s = max(0, stem - J_HOOK)
    if s:
        px = [px[y * W + x + s] if x + s < W else 0 for y in range(H) for x in range(W)]
        f.set_pixels(g, px)
    return f


def embolden_halfwidth(f):
    """Make the (left-aligned) ASCII glyphs bold: every ink pixel also inks the pixel to its right.

    The game's half-width Latin glyphs are 1 px strokes; doubling vertical stems gives the weight of
    the Skies of Arcadia font used by the Seireiki Rayblade patch, while staying the game's own
    letter shapes. Level 2 is full ink in this font; the added pixel takes the source pixel's level.
    """
    for b in range(0x21, 0x7F):
        g = f.index(ascii_to_sjis(b))
        if g is None:
            continue
        px = f.get_pixels(g)
        new = list(px)
        for y in range(H):
            for x in range(1, W):
                left = px[y * W + x - 1]
                if left > new[y * W + x]:
                    new[y * W + x] = left
        f.set_pixels(g, new)
    return f


def build_table(font_path_or_ufm):
    f = font_path_or_ufm if isinstance(font_path_or_ufm, UFM) else UFM(font_path_or_ufm)
    tab = bytearray(256)
    for b in range(0x20, 0x100):
        tab[b] = 10                       # default: original half width
    for b in range(0x21, 0x7F):
        w = glyph_width(f, ascii_to_sjis(b))
        if w:
            tab[b] = min(w, 20)
    tab[0x20] = SPACE_WIDTH
    for k, v in FIXED.items():
        tab[k] = v
    return bytes(tab)


MAGIC = 0x5756            # 'VW' stored as u16 at font header +6
MAGIC_OFF = 6
TABLE_PTR_OFF = 8         # u32 offset of the 256-byte width table inside the font file
FONT_DATA_FIELD = 0x484   # CUmeStdFont: pointer to the loaded .ufm
FONT_METRIC_FIELD = 0x450  # CUmeStdFont: metrics struct, +4 = full width


def halfwidth_patch():
    """Replacement for HalfWidth(font a0, byte a1) at 0x197BF0 (16 words available)."""
    from asm import asm
    code = asm([
        'andi $v0, $a1, 0xff',
        'lw $v1, 0x%X($a0)' % FONT_DATA_FIELD,
        'beqz $v1, fallback',
        'nop',
        'lhu $t0, %d($v1)' % MAGIC_OFF,
        'ori $t1, $zero, 0x%X' % MAGIC,
        'bne $t0, $t1, fallback',
        'lw $t2, %d($v1)' % TABLE_PTR_OFF,
        'addu $v1, $v1, $t2',
        'addu $v1, $v1, $v0',
        'jr $ra',
        'lbu $v0, 0($v1)',
        'fallback:',
        'lw $v0, 0x%X($a0)' % FONT_METRIC_FIELD,
        'lw $v0, 4($v0)',
        'jr $ra',
        'sra $v0, $v0, 1',
    ], HALFWIDTH_FN)
    assert len(code) <= HALFWIDTH_FN_SIZE, len(code)
    return code


# Extra single-byte glyphs: half-width katakana codes (unused by the English script) redrawn as
# punctuation. 0xA1 = comma for CSV files, where a real ',' would split the cell.
EXTRA = {0xA1: ord(',')}


def add_extra_glyphs(f, tab):
    from ufm_tool import sjis_to_jis
    for code, src in EXTRA.items():
        gs = f.index(src)
        gd = f.index(code)
        if gs is None or gd is None:
            raise RuntimeError('extra glyph slot missing for 0x%X' % code)
        f.set_pixels(gd, f.get_pixels(gs))
        tab[code] = tab[src]


def build_font(src_path):
    """Return patched .ufm bytes: left-aligned ASCII glyphs + width table + header magic."""
    f = fix_l_glyph(fix_j_hook(left_align_halfwidth(UFM(src_path))))
    if BOLD:
        f = embolden_halfwidth(f)
    tab = bytearray(build_table(f))
    add_extra_glyphs(f, tab)
    tab = bytes(tab)
    data = f.data
    off = len(data)
    off = (off + 15) & ~15
    data += b'\0' * (off - len(data)) + tab
    struct.pack_into('<H', data, MAGIC_OFF, MAGIC)
    struct.pack_into('<I', data, TABLE_PTR_OFF, off)
    return bytes(data), tab


def patch_words(table_addr):
    hi = ((table_addr + 0x8000) >> 16) & 0xFFFF
    lo = table_addr & 0xFFFF
    return [
        0x30A200FF,               # andi v0, a1, 0xff
        0x3C030000 | hi,          # lui  v1, hi
        0x00621821,               # addu v1, v1, v0
        0x03E00008,               # jr   ra
        0x90620000 | lo,          # lbu  v0, lo(v1)
    ]


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'table':
        t = build_table(a[1])
        open(a[2], 'wb').write(t)
        if '--json' in a:
            json.dump({chr(i): t[i] for i in range(0x20, 0x7F)}, open(a[a.index('--json') + 1], 'w'), indent=0)
        print(' '.join('%s=%d' % (chr(i), t[i]) for i in range(0x20, 0x7F)))
    elif a[0] == 'code':
        print(' '.join('%08X' % w for w in patch_words(int(a[1], 16))))
