"""Corpus-wide name / term fixes, run AFTER agent review edits (BASE_RULES: agents first, names last).

Each rule: (regex, replacement, optional Japanese condition). Applies to strings.json "en" and the
card fields in cards.json. Dry run unless --apply; every change is logged in the row history.

python tools/names_fix.py [--apply]
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, 'work', 'translation', 'en')

RULES = [
    # ranks: 少尉 = Ensign (official site usage), 中尉 = Lieutenant
    (r'\b2nd Lt\.', 'Ensign', '少尉'),
    (r'^Made 1st Lt\.$', 'Made Lieutenant', '中尉'),
    (r'^1st Lt\.$', 'Lieutenant', '中尉'),
    # one name per unit (official site: Hizack (E.F.S.F.))
    (r'Hizack \(Federation Forces\)', 'Hizack (E.F.S.F.)', None),
    (r'Hizack \(Federation\)', 'Hizack (E.F.S.F.)', None),
    # glossary personality tag
    (r'Hot-Blooded', 'Hot-blooded', None),
    # stale wiki spellings replaced by official ones
    (r'\bGinias\b', 'Ginius', None), (r'\bSahalin\b', 'Sakhalin', None), (r'\bApolly\b', 'Aboly', None),
    (r'\bQueen Mansa\b', 'Quin Mantha', None), (r'\bPle Two\b', 'Ple-Two', None),
    (r'\bJacqueline Simone\b', 'Jacqueline Simon', None), (r'\bHyaku Shiki\b', 'Hyaku-Shiki', None),
]


def fix(text, jp):
    for pat, rep, cond in RULES:
        if cond and cond not in jp:
            continue
        text = re.sub(pat, rep, text)
    return text


def main(apply):
    rows = json.load(open(os.path.join(TR, 'strings.json'), encoding='utf-8'))
    cards = json.load(open(os.path.join(TR, 'cards.json'), encoding='utf-8'))
    n = 0
    for r in rows:
        en = r.get('en') or ''
        new = fix(en, r['jp'])
        if new != en:
            n += 1
            print('%s: %r -> %r' % (r['id'], en, new))
            if apply:
                r.setdefault('history', []).append({'stage': 'names', 'old': en, 'reason': 'names_fix.py'})
                r['en'] = new
        if r['id'] == r['id']:
            for o in r['occ']:
                if o.get('en_override'):
                    o['en_override'] = fix(o['en_override'], r['jp'])
    for c in cards:
        jp = ' '.join([c['name_jp'], c['model_jp']] + c['desc_jp_lines'])
        for k in ('name_en', 'label_en', 'model_en', 'desc_en'):
            v = c.get(k) or ''
            new = fix(v, jp)
            if new != v:
                n += 1
                print('%s.%s: %r -> %r' % (c['id'], k, v, new))
                if apply:
                    c.setdefault('history', []).append({'stage': 'names', 'old': {k: v}, 'reason': 'names_fix.py'})
                    c[k] = new
    if apply:
        json.dump(rows, open(os.path.join(TR, 'strings.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        json.dump(cards, open(os.path.join(TR, 'cards.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('%d changes %s' % (n, 'applied' if apply else '(dry run)'))


if __name__ == '__main__':
    main('--apply' in sys.argv)
