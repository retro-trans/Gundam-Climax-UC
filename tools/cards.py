"""Card gallery (encyclopedia) text: card_info.inf <-> work/translation/en/cards.json.

card_info.inf: u32 count (423), then 400-byte records:
  +0x000 char[8]   id ("U-01"; U unit, P pilot, C character, B BGM, M movie, S stage, H history)
  +0x008 char[40]  name
  +0x030 char[44]  label ("U01 ガンダム")
  +0x05C char[44]  model / sub line
  +0x088 char[44]  description line 1 ... 6 lines, 0x2C apart (unused lines hold " ")
The description is one paragraph wrapped by the original writers; the English is stored as
one paragraph and re-wrapped here by rendered pixel width (VWF table).

Usage:
  python cards.py extract      (keeps existing "en" fields)
"""
import json
import os
import struct
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

SRC = os.path.join(ROOT, 'work', 'source', 'game', 'card_info.inf')
OUT = os.path.join(ROOT, 'work', 'translation', 'en', 'cards.json')
RS = 400
F_NAME, F_LABEL, F_MODEL = (0x08, 40), (0x30, 44), (0x5C, 44)
LINES = [0x88 + 0x2C * i for i in range(6)]
LINE_SIZE = 44
LINE_PX = 380          # widest original line: 19 full-width chars x 20 px (panel x=30..410, checked on screen)
# lines actually drawn per card type (checked in the Unit Viewer: lines 3+ ignored for U cards)
MAX_LINES = {'U': 2, 'P': 2, 'C': 2, 'B': 2, 'M': 2, 'S': 2, 'H': 6}


def _s(r, off, size):
    return r[off:off + size].split(b'\0')[0].decode('cp932')


def read_cards(path=SRC):
    d = open(path, 'rb').read()
    n = struct.unpack_from('<I', d)[0]
    cards = []
    for k in range(n):
        r = d[4 + k * RS: 4 + (k + 1) * RS]
        lines = [_s(r, o, LINE_SIZE) for o in LINES]
        used = [l for l in lines if l.strip()]
        cards.append({'id': _s(r, 0, 8), 'index': k,
                      'name_jp': _s(r, *F_NAME), 'label_jp': _s(r, *F_LABEL), 'model_jp': _s(r, *F_MODEL),
                      'desc_jp_lines': lines, 'lines_used': len(used)})
    return cards


def extract():
    old = {}
    if os.path.exists(OUT):
        for c in json.load(open(OUT, encoding='utf-8')):
            old[c['id']] = c
    out = []
    for c in read_cards():
        o = old.get(c['id'], {})
        c.update({'name_en': o.get('name_en', ''), 'label_en': o.get('label_en', ''),
                  'model_en': o.get('model_en', ''), 'desc_en': o.get('desc_en', ''), 'note': o.get('note', '')})
        out.append(c)
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('cards', len(out))


def build(cards_json=OUT, src=SRC, nlines=None):
    """Return patched card_info.inf bytes and a list of problems."""
    import textenc
    d = bytearray(open(src, 'rb').read())
    probs = []
    for c in json.load(open(cards_json, encoding='utf-8')):
        base = 4 + c['index'] * RS
        for key, (off, size) in (('name_en', F_NAME), ('label_en', F_LABEL), ('model_en', F_MODEL)):
            if c.get(key):
                b = textenc.encode(c[key])
                if len(b) > size - 1:
                    probs.append('%s %s too long (%d>%d)' % (c['id'], key, len(b), size - 1))
                    continue
                d[base + off: base + off + size] = b + b'\0' * (size - len(b))
        if c.get('desc_en'):
            maxl = nlines or MAX_LINES.get(c['id'][0], 2)
            lines = textenc.wrap(c['desc_en'], LINE_PX, LINE_SIZE - 1)
            if len(lines) > maxl:
                probs.append('%s desc needs %d lines > %d' % (c['id'], len(lines), maxl))
                continue
            lines += [' '] * (6 - len(lines))
            for o, l in zip(LINES, lines):
                b = textenc.encode(l)
                d[base + o: base + o + LINE_SIZE] = b + b'\0' * (LINE_SIZE - len(b))
    return bytes(d), probs


if __name__ == '__main__':
    if sys.argv[1] == 'extract':
        extract()
