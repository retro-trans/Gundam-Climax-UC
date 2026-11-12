"""Cut translation work into slices for translator agents, and merge their results back.

  python slices.py make            -> work/translation/en/slices/<name>.json (+ index.json)
  python slices.py merge [names]   <- work/translation/en/slices/out/<name>.json
  python slices.py status

Slice input row:  {"id", "jp", "max_bytes", "max_px"?, "where", "prev_id", "next_id"}
Slice output:     {"slice", "rows_in_slice", "rows_examined",
                   "rows": [{"id", "en", "note"?, "flag"?}], "decisions": [...], "uncertain": [...]}
Card slices use card ids and fields name_en/label_en/model_en/desc_en instead of "en".
Rows whose output carries "flag" are not merged (left for follow-up).
"""
import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

TR = os.path.join(ROOT, 'work', 'translation', 'en')
SL = os.path.join(TR, 'slices')
OUTD = os.path.join(SL, 'out')

PLAN = [  # group, rows per slice
    ('mission_intro', 80), ('briefing', 80), ('history', 80),
    ('stage', 145), ('ui', 210), ('data', 205), ('elf', 75),
]


def where(o):
    if 'path' not in o:
        return 'SLPS_256.27 @%s (slot %d bytes)' % (o['addr'], o['slot'])
    if o['kind'] == 'csv':
        return '%s line %d' % (o['path'], o['line'])
    return '%s %s' % (o['path'], o.get('ctx', ''))


def make(only=None):
    os.makedirs(SL, exist_ok=True)
    os.makedirs(OUTD, exist_ok=True)
    rows = json.load(open(os.path.join(TR, 'strings.json'), encoding='utf-8'))
    index = []
    if only:
        index = [i for i in json.load(open(os.path.join(SL, 'index.json'))) if i['group'] not in only]
    for group, n in PLAN:
        if only and group not in only:
            continue
        g = [r for r in rows if r['group'] == group and not r.get('en')]
        for k in range(0, len(g), n):
            part = g[k:k + n]
            name = '%s_%02d' % (group, k // n + 1)
            out = []
            for i, r in enumerate(part):
                row = {'id': r['id'], 'jp': r['jp'], 'max_bytes': r['max'],
                       'where': [where(o) for o in r['occ'][:3]] + (['+%d more' % (len(r['occ']) - 3)] if len(r['occ']) > 3 else [])}
                elf = [o['slot'] for o in r['occ'] if 'path' not in o]
                if elf:
                    row['slot_bytes'] = min(elf) - 1
                out.append(row)
            json.dump({'slice': name, 'group': group, 'rows': out,
                       'prev_slice': index[-1]['name'] if index and index[-1]['group'] == group else None},
                      open(os.path.join(SL, name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            index.append({'name': name, 'group': group, 'rows': len(out), 'first': out[0]['id'], 'last': out[-1]['id']})
    if only:
        json.dump(index, open(os.path.join(SL, 'index.json'), 'w'), indent=1)
        print('slices', len(index))
        return
    import cards as C
    cs = [c for c in json.load(open(os.path.join(TR, 'cards.json'), encoding='utf-8')) if not c.get('desc_en')]
    for k in range(0, len(cs), 106):
        part = cs[k:k + 106]
        name = 'cards_%02d' % (k // 106 + 1)
        out = [{'id': c['id'], 'name_jp': c['name_jp'], 'label_jp': c['label_jp'], 'model_jp': c['model_jp'],
                'desc_jp': ''.join(l for l in c['desc_jp_lines'] if l.strip()),
                'desc_lines_max': C.MAX_LINES.get(c['id'][0], 2), 'line_px': C.LINE_PX, 'line_bytes': C.LINE_SIZE - 1,
                'name_bytes': 39, 'label_bytes': 43, 'model_bytes': 43} for c in part]
        json.dump({'slice': name, 'group': 'cards', 'rows': out}, open(os.path.join(SL, name + '.json'), 'w',
                                                                       encoding='utf-8'), ensure_ascii=False, indent=1)
        index.append({'name': name, 'group': 'cards', 'rows': len(out), 'first': out[0]['id'], 'last': out[-1]['id']})
    json.dump(index, open(os.path.join(SL, 'index.json'), 'w'), indent=1)
    for i in index:
        print('%-18s %4d rows' % (i['name'], i['rows']))
    print('slices', len(index))


def merge(names=None):
    rows = json.load(open(os.path.join(TR, 'strings.json'), encoding='utf-8'))
    byid = {r['id']: r for r in rows}
    cards = json.load(open(os.path.join(TR, 'cards.json'), encoding='utf-8'))
    cbyid = {c['id']: c for c in cards}
    n = flagged = 0
    for fn in sorted(os.listdir(OUTD)):
        name = fn[:-5]
        if names and name not in names:
            continue
        res = json.load(open(os.path.join(OUTD, fn), encoding='utf-8'))
        for r in res['rows']:
            if r.get('flag'):
                flagged += 1
                continue
            if r['id'] in cbyid:
                c = cbyid[r['id']]
                for k in ('name_en', 'label_en', 'model_en', 'desc_en', 'note'):
                    if r.get(k):
                        c[k] = r[k]
                n += 1
            elif r['id'] in byid and r.get('en'):
                byid[r['id']]['en'] = r['en']
                if r.get('note'):
                    byid[r['id']]['note'] = r['note']
                n += 1
    json.dump(rows, open(os.path.join(TR, 'strings.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(cards, open(os.path.join(TR, 'cards.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('merged', n, 'flagged (not merged)', flagged)


def status():
    rows = json.load(open(os.path.join(TR, 'strings.json'), encoding='utf-8'))
    cards = json.load(open(os.path.join(TR, 'cards.json'), encoding='utf-8'))
    print('strings %d/%d translated, cards %d/%d' % (sum(1 for r in rows if r.get('en')), len(rows),
                                                    sum(1 for c in cards if c.get('desc_en')), len(cards)))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'make':
        make(a[1:] or None)
    else:
        {'status': status}.get(a[0], lambda: merge(a[1:] or None))()
