"""Apply translations to GAME.MB entries.

build_all() -> {top-level GAME.MB entry name: new bytes}
  - strings.json rows with "en" (c2b / rec / csv occurrences)
  - cards.json (card_info.inf)
Problems (too long, bad characters) are collected in work/build/insert_report.txt; such rows
are left in Japanese, never cut.

Usage: python insert_text.py   (dry run: writes the report and prints a summary)
"""
import collections
import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import cards  # noqa: E402
import fpk_tool  # noqa: E402
import textenc  # noqa: E402
import textlib  # noqa: E402

SRC_GAME = os.path.join(ROOT, 'work', 'source', 'game')
STRINGS = os.path.join(ROOT, 'work', 'translation', 'en', 'strings.json')
REPORT = os.path.join(ROOT, 'work', 'build', 'insert_report.txt')
CSV_COMMA = b'\xA1'   # drawn as ',' by the patched font (vwf.EXTRA)


def locate(data, parts):
    """Absolute (offset, size) of a nested FPK member path inside data."""
    off = 0
    cur = data
    for p in parts:
        f = fpk_tool.parse(cur)
        m = next(e for e in f['entries'] if e['name'] == p)
        moff = f['dstart'] + m['offset']
        off += moff
        cur = cur[moff: moff + m['size']]
    return off, len(cur)


def locate_all(data, parts, base=0):
    """Absolute offsets of every member matching a nested path. FPKs can hold several members with
    the same name (e.g. vs_setting2.fpk has two vs_setting2.inf); extraction reports them under one
    path, so insertion must patch each copy."""
    if not parts:
        return [base]
    f = fpk_tool.parse(data)
    out = []
    for m in f['entries']:
        if m['name'] == parts[0]:
            moff = f['dstart'] + m['offset']
            out += locate_all(data[moff:moff + m['size']], parts[1:], base + moff)
    return out


def encode_csv(s):
    return textenc.encode(s).replace(b',', CSV_COMMA)


def build_qcsv(orig, edits, probs):
    """Rebuild a quoted CSV (one message per record, CRLF between records). Edited cells are
    written with the file's own in-cell line-break style; commas use the 0xA1 comma glyph; cells
    holding a line break are quoted, as in the original."""
    CR, LF = '\r', '\n'
    recs = textlib.qcsv_records(orig)
    raw = orig.decode('cp932')
    nl = CR + LF if any(CR + LF in c for r in recs for c in r) else LF
    out = []
    for ri, rec in enumerate(recs):
        cells = []
        for ci, c in enumerate(rec):
            ro = edits.get((ri, ci))
            if ro:
                r, o = ro
                text = (o.get('en_override') or r['en']).replace(CR + LF, LF).replace(LF, nl)
                try:
                    b = encode_csv(textenc.recentre(r['jp'], text))
                except UnicodeEncodeError as e:
                    probs.append('%s %s: unencodable %s' % (r['id'], o['path'], e))
                    b = c.encode('cp932')
            else:
                b = c.encode('cp932')
            if LF.encode() in b or b'"' in b:
                b = b'"' + b.replace(b'"', b'""') + b'"'
            cells.append(b)
        out.append(b','.join(cells))
    tail = (CR + LF).encode() if raw.endswith(CR + LF) else b''
    return (CR + LF).encode().join(out) + tail


def build_all(report_path=REPORT):
    probs = []
    out = {}
    rows = json.load(open(STRINGS, encoding='utf-8')) if os.path.exists(STRINGS) else []
    by_top = collections.defaultdict(list)
    for r in rows:
        if not r.get('en'):
            continue
        for o in r['occ']:
            if 'path' not in o:   # executable text: tools/elf_text.py, applied by build.py
                continue
            by_top[o['path'].split('/')[0]].append((r, o))
    for top, items in sorted(by_top.items()):
        orig = open(os.path.join(SRC_GAME, top), 'rb').read()
        data = bytearray(orig)
        csv_edits = collections.defaultdict(dict)
        qcsv_edits = collections.defaultdict(dict)
        for r, o in items:
            parts = o['path'].split('/')[1:]
            if o['kind'] == 'qcsv':
                qcsv_edits[o['path']][(o['rec'], o['cell'])] = (r, o)
                continue
            if o['kind'] == 'csv':
                csv_edits[o['path']][(o['line'], o['cell'])] = (r, o)
                continue
            try:
                b = textenc.encode(textenc.recentre(r['jp'], r['en'], o['max']))
            except UnicodeEncodeError as e:
                probs.append('%s %s: unencodable %s' % (r['id'], o['path'], e))
                continue
            if len(b) > o['max']:
                probs.append('%s %s +%X: %d bytes > %d' % (r['id'], o['path'], o['off'], len(b), o['max']))
                continue
            jpb = r['jp'].encode('cp932')
            hit = 0
            for base in locate_all(orig, parts):
                a = base + o['off']
                if orig[a:a + len(jpb)] != jpb:   # a same-named member with a different layout
                    continue
                data[a:a + o['max'] + 1] = b + b'\0' * (o['max'] + 1 - len(b))
                hit += 1
            if not hit:
                probs.append('%s %s +%X: source text not found' % (r['id'], o['path'], o['off']))
        for path, edits in qcsv_edits.items():
            if '/' in path:
                probs.append('%s: quoted CSV inside FPK not supported' % path)
                continue
            data = bytearray(build_qcsv(bytes(data), edits, probs))
        for path, edits in csv_edits.items():
            if '/' in path:
                probs.append('%s: CSV inside FPK not supported' % path)
                continue
            lines = bytes(data).decode('cp932').split('\r\n')
            out_lines = []
            for li, line in enumerate(lines):
                cells = line.split(',')
                enc = [c.encode('cp932') for c in cells]
                for ci in range(len(cells)):
                    ro = edits.get((li, ci))
                    if ro:
                        r, oc = ro
                        # a shared row can carry a per-occurrence override (e.g. sentence-initial "The")
                        r = dict(r, en=oc.get('en_override') or r['en'])
                        try:
                            enc[ci] = encode_csv(textenc.recentre(r['jp'], r['en']))
                        except UnicodeEncodeError as e:
                            probs.append('%s %s: unencodable %s' % (r['id'], path, e))
                out_lines.append(b','.join(enc))
            data = bytearray(b'\r\n'.join(out_lines))
        out[top] = bytes(data)
    # cards
    cpath = os.path.join(ROOT, 'work', 'translation', 'en', 'cards.json')
    if os.path.exists(cpath):
        d, p = cards.build(cpath)
        probs += p
        if d != open(cards.SRC, 'rb').read():
            out['card_info.inf'] = d
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    open(report_path, 'w', encoding='utf-8').write('\n'.join(probs) + '\n')
    if probs:
        print('insert: %d problems, see %s' % (len(probs), report_path))
    return out


if __name__ == '__main__':
    o = build_all()
    print('entries changed:', len(o))
    for k in sorted(o):
        print('  ', k)
