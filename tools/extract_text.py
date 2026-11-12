"""Extract all translatable text from GAME.MB into work/translation/en/strings.json.

strings.json: list of unique source strings in first-seen order:
  {"id": "S00001", "jp": ..., "en": "", "group": <category>, "max": <min byte budget>,
   "occ": [occurrence dicts without jp]}
Existing "en" values in the output file are preserved (keyed by jp).

Also writes work/source/scan/text_inventory.txt (per-file counts).
Usage: python extract_text.py
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textlib  # noqa: E402
import elf_text  # noqa: E402

OUT = os.path.join(textlib.ROOT, 'work', 'translation', 'en', 'strings.json')


def group_of(path):
    p = path.lower()
    if p.startswith('card_info'):
        return 'encyclopedia'
    if p.startswith('mcd_msg'):
        return 'system'
    if p.startswith(('mp_cn_', 'mp_pr_')) and p.endswith('.inf'):
        return 'mission_intro'
    if 'briefing' in p:
        return 'briefing'
    if p.startswith('info_data') or p.startswith('unit_data'):
        return 'data'
    if p.startswith('history'):
        return 'history'
    if p.startswith(('chronicle', 'ex_stage', 'vs_stage', 'scenes')):
        return 'stage'
    return 'ui'


def main():
    old = {}
    if os.path.exists(OUT):
        for r in json.load(open(OUT, encoding='utf-8')):
            old[r['jp']] = r
    # row ids are permanent: known Japanese keeps its id, new Japanese gets the next free number
    # (ids are referenced by review logs, overrides and docs)
    next_id = [max([int(r['id'][1:]) for r in old.values()] or [0]) + 1]

    def new_id(jp):
        if jp in old:
            return old[jp]['id']
        i = next_id[0]
        next_id[0] += 1
        return 'S%05d' % i

    rows = collections.OrderedDict()
    inv = collections.Counter()
    for path, data in textlib.iter_mb_files():
        try:
            occ = textlib.extract_file(path, data)
        except Exception as e:  # noqa
            print('ERR', path, e)
            continue
        for o in occ:
            jp = o.pop('jp')
            if 'max' in o and o['max'] < len(jp.encode('cp932')):
                continue  # not a real slot (binary noise)
            inv[path] += 1
            r = rows.get(jp)
            if r is None:
                r = rows[jp] = {'id': new_id(jp), 'jp': jp, 'en': '', 'group': group_of(path),
                                'max': None, 'occ': []}
                if jp in old:
                    r['en'] = old[jp].get('en', '')
                    for k in ('note', 'status', 'history'):
                        if k in old[jp]:
                            r[k] = old[jp][k]
            r['occ'].append(o)
            if 'max' in o:
                r['max'] = o['max'] if r['max'] is None else min(r['max'], o['max'])
    # player-facing text in the executable (no 'max': elf_text relocates strings longer than their slot)
    for o in elf_text.occurrences():
        jp = o.pop('jp')
        inv['SLPS_256.27'] += 1
        r = rows.get(jp)
        if r is None:
            r = rows[jp] = {'id': new_id(jp), 'jp': jp, 'en': '', 'group': 'elf', 'max': None, 'occ': []}
            if jp in old:
                r['en'] = old[jp].get('en', '')
                for k in ('note', 'status', 'history'):
                    if k in old[jp]:
                        r[k] = old[jp][k]
        r['occ'].append(o)
    # keep per-occurrence overrides (shared rows that must read differently in one place)
    for jp, r in rows.items():
        if jp in old:
            ov = {(o.get('path'), o.get('line'), o.get('cell'), o.get('off')): o['en_override']
                  for o in old[jp]['occ'] if o.get('en_override')}
            for o in r['occ']:
                k = (o.get('path'), o.get('line'), o.get('cell'), o.get('off'))
                if k in ov:
                    o['en_override'] = ov[k]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = collections.OrderedDict(sorted(rows.items(), key=lambda kv: kv[1]['id']))
    json.dump(list(rows.values()), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(os.path.join(textlib.ROOT, 'work', 'source', 'scan', 'text_inventory.txt'), 'w', encoding='utf-8') as f:
        for p, c in sorted(inv.items()):
            f.write('%5d  %s\n' % (c, p))
    g = collections.Counter(r['group'] for r in rows.values())
    print('unique strings', len(rows), 'occurrences', sum(inv.values()), dict(g))
    print('chars', sum(len(r['jp']) for r in rows.values()))


if __name__ == '__main__':
    main()
