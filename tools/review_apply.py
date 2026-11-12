"""Apply review-stage edits to strings.json (dry run unless --apply).

python tools/review_apply.py <stage> [part ...] [--apply]
reads work/translation/en/review/out/<stage>_<part>.json (all parts of the stage by default).
Each applied edit is logged in the row's "history" list: {"stage", "old", "reason"}.
Two different edits to one row are both reported and NOT applied (resolve by hand).
"""
import collections, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, 'work', 'translation', 'en')
OUTD = os.path.join(TR, 'review', 'out')


def main(stage, parts, apply):
    files = [os.path.join(OUTD, '%s_%s.json' % (stage, p)) for p in parts] if parts else \
        sorted(glob.glob(os.path.join(OUTD, stage + '_*.json')))
    edits = collections.defaultdict(list)
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        for e in d.get('edits', []):
            edits[e['id']].append((os.path.basename(f), e))
    rows = json.load(open(os.path.join(TR, 'strings.json'), encoding='utf-8'))
    by = {r['id']: r for r in rows}
    cpath = os.path.join(TR, 'cards.json')
    cards = json.load(open(cpath, encoding='utf-8'))
    cards_by = {c['id']: c for c in cards}
    n = bad = 0
    for i, lst in sorted(edits.items()):
        news = {e.get('en') for _, e in lst}
        if i in cards_by:
            c = cards_by[i]
            e = lst[0][1]
            if len(lst) > 1:
                print('CONFLICT', i, [f for f, _ in lst]); bad += 1; continue
            ch = {k: e[k] for k in ('name_en', 'label_en', 'model_en', 'desc_en') if k in e and e[k] != c.get(k)}
            if not ch:
                continue
            print('%s card %s  (%s)' % (i, ch, e.get('reason', '')))
            n += 1
            if apply:
                c.setdefault('history', []).append({'stage': stage, 'old': {k: c.get(k) for k in ch}, 'reason': e.get('reason', '')})
                c.update(ch)
            continue
        r = by.get(i)
        if r is None:
            print('UNKNOWN id', i, [f for f, _ in lst]); bad += 1; continue
        if len(news) > 1:
            print('CONFLICT', i, [(f, e['en']) for f, e in lst]); bad += 1; continue
        new = news.pop()
        try:
            new.encode('ascii')
        except UnicodeEncodeError:
            print('NON-ASCII', i, new); bad += 1; continue
        if r.get('max') is not None and len(new) > r['max']:
            print('TOO LONG', i, len(new), '>', r['max'], new); bad += 1; continue
        if new == r.get('en'):
            continue
        print('%s\n  - %s\n  + %s\n    (%s)' % (i, r.get('en', '').replace('\n', ' / '), new.replace('\n', ' / '),
                                             lst[0][1].get('reason', '')))
        n += 1
        if apply:
            r.setdefault('history', []).append({'stage': stage, 'old': r.get('en', ''), 'reason': lst[0][1].get('reason', '')})
            r['en'] = new
    if apply:
        json.dump(rows, open(os.path.join(TR, 'strings.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        json.dump(cards, open(cpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        # applied outputs move aside so a later run of the same stage cannot re-apply stale edits
        done = os.path.join(OUTD, 'applied')
        os.makedirs(done, exist_ok=True)
        for f in files:
            os.replace(f, os.path.join(done, os.path.basename(f)))
    print('%s: %d edits %s, %d problems' % (stage, n, 'applied' if apply else 'would apply (dry run)', bad))


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(a[0], a[1:], '--apply' in sys.argv)
