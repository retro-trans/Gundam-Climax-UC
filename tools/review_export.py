"""Export translated text in scene order for the review stages.

Mission intros: one block per mp_*.inf file, lines in display order (shared rows appear in every
file that uses them, so a reviewer sees each join). Other groups: one block per source file,
rows in file order.

python tools/review_export.py <group> [group...]   -> work/translation/en/review/<group>.txt
Line format:  <id> | JP: ... | EN: ...      (\n shown as ' / ')
"""
import collections, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, 'work', 'translation', 'en')


PARTS = {'mission_intro': 6}
ROWS_PER_PART = 260   # other groups: unique rows in first-seen (file) order


def esc(s):
    return s.replace('\n', ' / ')


def export_rows(group):
    rows = [r for r in json.load(open(os.path.join(TR, 'strings.json'), encoding='utf-8'))
            if r['group'] == group and r.get('status') != 'not_text']
    os.makedirs(os.path.join(TR, 'review'), exist_ok=True)
    parts = max(1, round(len(rows) / ROWS_PER_PART))
    per = -(-len(rows) // parts)
    for k in range(parts):
        chunk = rows[k * per:(k + 1) * per]
        out = []
        for r in chunk:
            o = r['occ'][0]
            where = o.get('path') or 'SLPS_256.27@' + o.get('addr', '')
            extra = ' (+%d more)' % (len(r['occ']) - 1) if len(r['occ']) > 1 else ''
            lim = ' max=%s' % r['max'] if r.get('max') is not None else ''
            out.append('%s | %s%s%s | JP: %s | EN: %s' % (r['id'], where, extra, lim, esc(r['jp']), esc(r.get('en', ''))))
        name = '%s_%d' % (group, k + 1) if parts > 1 else group
        p = os.path.join(TR, 'review', name + '.txt')
        open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
        print(p, len(chunk), 'rows')


def export(group):
    if group != 'mission_intro':
        return export_rows(group)
    rows = json.load(open(os.path.join(TR, 'strings.json'), encoding='utf-8'))
    files = collections.defaultdict(list)
    for r in rows:
        if r['group'] != group:
            continue
        for o in r['occ']:
            src = o.get('path') or 'SLPS_256.27'
            key = o.get('line', o.get('off', o.get('addr', 0)))
            if isinstance(key, str):
                key = int(key, 16)
            files[src].append((key, o.get('cell', 0), r))
    used = collections.defaultdict(set)
    for f, v in files.items():
        for _, _, r in v:
            used[r['id']].add(f)
    out = []
    blocks = []
    for f in sorted(files):
        out = []
        out.append('=== %s' % f)
        seen = set()
        for k, c, r in sorted(files[f], key=lambda x: (x[0], x[1])):
            if (k, r['id']) in seen:
                continue
            seen.add((k, r['id']))
            sh = sorted(used[r['id']] - {f})
            tag = '  [shared, also in: %s]' % ', '.join(sh) if sh else ''
            out.append('%s | JP: %s | EN: %s%s' % (r['id'], esc(r['jp']), esc(r.get('en', '')), tag))
        out.append('')
        blocks.append(out)
    os.makedirs(os.path.join(TR, 'review'), exist_ok=True)
    parts = PARTS.get(group, 1)
    per = -(-len(blocks) // parts)
    for k in range(parts):
        chunk = blocks[k * per:(k + 1) * per]
        name = '%s_%d' % (group, k + 1) if parts > 1 else group
        p = os.path.join(TR, 'review', name + '.txt')
        open(p, 'w', encoding='utf-8').write('\n'.join(l for b in chunk for l in b))
        print(p, len(chunk), 'files', sum(len(b) - 2 for b in chunk), 'lines')




def export_cards(parts=4):
    import sys as _s
    _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import cards as C
    cs = json.load(open(os.path.join(TR, 'cards.json'), encoding='utf-8'))
    per = -(-len(cs) // parts)
    for k in range(parts):
        out = []
        for c in cs[k * per:(k + 1) * per]:
            out.append('%s | lines_max=%d | NAME JP: %s | EN: %s | LABEL EN: %s' % (
                c['id'], C.MAX_LINES.get(c['id'][0], 2), c['name_jp'], c.get('name_en', ''), c.get('label_en', '')))
            out.append('    MODEL JP: %s | EN: %s' % (c['model_jp'], c.get('model_en', '')))
            out.append('    DESC  JP: %s' % ''.join(l for l in c['desc_jp_lines'] if l.strip()))
            out.append('    DESC  EN: %s' % c.get('desc_en', ''))
        p = os.path.join(TR, 'review', 'cards_%d.txt' % (k + 1))
        open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
        print(p, len(cs[k * per:(k + 1) * per]), 'cards')


if __name__ == '__main__':
    for g in sys.argv[1:]:
        export_cards() if g == 'cards' else export(g)
