"""Compare glossary spellings with the official English site (work/glossary/_official_names.json).

python tools/official_check.py            -> report only
python tools/official_check.py --apply    -> set en to the official spelling where a confident match differs
"""
import difflib, json, re, sys, unicodedata

G = 'work/glossary/'
off = json.load(open(G + '_official_names.json', encoding='utf8'))


def norm(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', s.lower())


def split_names(n):
    # "Quattro Bajeena / Char Aznable", "Rosamia Badam (Rosamy Badam)", "RASARA MOON/Rasara Moon"
    parts = re.split(r'\s*/\s*|\s*\(', n)
    return [p.strip(' )') for p in parts if p.strip(' )')]


def pool(kind):
    out = {}
    for k, v in off.items():
        if k.endswith('/' + kind):
            for n in v:
                for p in split_names(n):
                    out.setdefault(norm(p), (p, k))
    return out


def main(apply):
    rep = []
    for fn, kind in (('characters.json', 'character'), ('mobile_suits.json', 'mecha')):
        data = json.load(open(G + fn, encoding='utf8'))
        P = pool(kind)
        keys = list(P)
        for e in data:
            en = e.get('en', '')
            if not en or norm(en) in P:
                if en and norm(en) in P:
                    e['official'] = P[norm(en)][1]
                continue
            # first-name/surname partial (e.g. Ple Two vs Ple-Two) handled by norm; otherwise fuzzy
            m = difflib.get_close_matches(norm(en), keys, n=1, cutoff=0.8)
            if m:
                p, src = P[m[0]]
                rep.append('%s\t%s\t-> %s\t(%s)' % (fn, en, p, src))
                if apply:
                    if e.get('note'):
                        e['note'] += ' '
                    e['note'] = (e.get('note') or '') + 'Wiki spelling: %s.' % en
                    e['en'] = p
                    e['official'] = src
                    e['source'] = 'https://en.gundam-official.com/series/' + src
        if apply:
            json.dump(data, open(G + fn, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print('\n'.join(rep))
    print('differences:', len(rep))


if __name__ == '__main__':
    main('--apply' in sys.argv)
