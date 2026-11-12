"""English text -> game bytes, plus pixel measuring and wrapping with the VWF table.

The game draws single-byte ASCII with the patched half-width glyphs (widths from vwf.py).
Typographic characters are folded to ASCII; anything else that is not cp932 raises.
Control codes / placeholders (%s, %d, \\n) pass through.
"""
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

FOLD = {
    '‘': "'", '’': "'", '“': '"', '”': '"', '—': '-', '–': '-',
    '…': '...', ' ': ' ', 'é': 'e', 'è': 'e', 'ü': 'u', 'ö': 'o',
    'Ⅰ': 'I', 'Ⅱ': 'II', 'Ⅲ': 'III', 'Ⅳ': 'IV',
}

_W = None


def widths():
    global _W
    if _W is None:
        import vwf
        _, tab = vwf.build_font(os.path.join(os.path.dirname(TOOLS), 'work', 'source', 'game', 's18rm04.ufm'))
        _W = tab
    return _W


def fold(s):
    return ''.join(FOLD.get(ch, ch) for ch in s)


def encode(s):
    return fold(s).encode('cp932')


FULL_PX = 18   # on-screen advance of a double-byte character (measured in the original game, 2026-11-10:
               # briefing header and stage-select title, 18 px per full-width cell; glyph cell is 20 px wide)


def px(s):
    """Rendered width in pixels (single line)."""
    w = widths()
    b = encode(s)
    total = 0
    i = 0
    while i < len(b):
        c = b[i]
        if c >= 0x81 and not 0xA0 <= c < 0xE0:
            total += FULL_PX
            i += 2
        else:
            total += w[c]
            i += 1
    return total


def wrap(text, max_px, max_bytes=None):
    """Greedy word wrap by pixels (and bytes). Explicit '\\n' forces a break."""
    out = []
    for para in fold(text).split('\n'):
        line = ''
        for word in para.split(' '):
            cand = word if not line else line + ' ' + word
            if px(cand) <= max_px and (max_bytes is None or len(encode(cand)) <= max_bytes):
                line = cand
            else:
                if line:
                    out.append(line)
                line = word
        out.append(line)
    return out


def jp_px(s):
    """Width of Japanese text in the ORIGINAL font metrics the Japanese layout was made for:
    double-byte FULL_PX (18), single-byte (ASCII / half-width kana) half of that."""
    return sum(FULL_PX if len(c.encode('cp932')) == 2 else FULL_PX // 2 for c in s)


def recentre(jp, en, max_bytes=None):
    """Re-create the Japanese alignment padding (leading full-width spaces) for English.

    Two layouts occur:
      * right-aligned blocks: two or more padded lines whose Japanese ends at the same x (briefing
        stage titles: every line is 17 full-width cells = 306 px). English lines get pad so they end
        at that x: pad_px = R - px(en).
      * otherwise centred: keep the Japanese line's centre, pad_px = pad + text/2 - en/2.
    Only full-width-space padding counts; ASCII-space indentation (history templates) is left alone.
    Pads are ASCII spaces. Padding is reduced, widest pads first, if the result exceeds max_bytes.
    """
    jl, el = jp.split('\n'), en.split('\n')
    if len(jl) != len(el):
        return en
    # 「 is drawn in the right half of its cell, so Japanese lines starting with it look indented;
    # an ASCII quote starts at the origin and touches box borders (chronicle stage titles). Add 1 space.
    el = [(' ' + e) if j.startswith('「') and e.startswith('"') else e for j, e in zip(jl, el)]
    sp = px(' ')
    padded =[j for j in jl if j.startswith('　') and j.strip('　 ')]
    ends = [jp_px(j.rstrip('　 ')) for j in padded]
    right = len(padded) >= 2 and max(ends) - min(ends) <= 10
    R = max(ends) if right else 0
    out = []
    for j, e in zip(jl, el):
        t = j.lstrip('　')
        if t == j or not t.strip() or not e.strip():
            out.append(e)
            continue
        e = e.strip()
        if right:
            pad_px = R - px(e)
        else:
            pad_px = jp_px(j[:len(j) - len(t)]) + jp_px(t.rstrip()) / 2.0 - px(e) / 2.0
        n = max(0, int(round(pad_px / sp)))
        out.append(' ' * n + e)
    res = '\n'.join(out)
    if max_bytes is not None:
        while len(encode(res)) > max_bytes and res != '\n'.join(l.lstrip() for l in res.split('\n')):
            lines = res.split('\n')
            k = max(range(len(lines)), key=lambda i: len(lines[i]) - len(lines[i].lstrip()))
            lines[k] = lines[k][1:]
            res = '\n'.join(lines)
    return res
