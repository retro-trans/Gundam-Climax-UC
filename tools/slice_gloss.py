"""Write a per-slice glossary excerpt: slices/<slice>.gloss.json holds only the glossary entries whose
Japanese name (or short name) occurs in that slice's Japanese text. Translators read this instead of
the whole glossary (saves ~50k tokens per agent). `en` here is already the form to write
(en_game when the font cannot draw en).

python tools/slice_gloss.py [slice ...]
"""
import glob, json, os, sys

G = 'work/glossary/'
S = 'work/translation/en/slices/'
KEEP = ('en_short', 'gender', 'role', 'personality', 'nickname', 'model', 'type', 'series', 'note')


def entries():
    out = []
    for fn, kind in (('characters.json', 'character'), ('mobile_suits.json', 'mobile_suit'), ('terms.json', None)):
        for e in json.load(open(G + fn, encoding='utf8')):
            keys = [k for k in (e.get('jp'), e.get('jp_short')) if k and len(k) >= 2]
            if not keys:
                continue
            c = {'jp': e['jp'], 'en': e.get('en_game') or e.get('en', '')}
            if kind:
                c['type'] = kind
            for k in KEEP:
                if e.get(k) and k not in c:
                    c[k] = e[k]
            if e.get('jp_short'):
                c['jp_short'] = e['jp_short']
            out.append((keys, c))
    return out


def slice_text(d):
    parts = []
    for r in d['rows']:
        for k, v in r.items():
            if k.endswith('jp') and isinstance(v, str):
                parts.append(v)
    return '\n'.join(parts)


def main(names):
    E = entries()
    files = [S + n + '.json' for n in names] if names else sorted(glob.glob(S + '*.json'))
    for f in files:
        if f.endswith(('index.json', '.gloss.json')):
            continue
        d = json.load(open(f, encoding='utf8'))
        t = slice_text(d)
        hits = [c for keys, c in E if any(k in t for k in keys)]
        out = f[:-5] + '.gloss.json'
        json.dump(hits, open(out, 'w', encoding='utf8'), ensure_ascii=False, indent=0)
        print(os.path.basename(out), len(hits), os.path.getsize(out))


if __name__ == '__main__':
    main(sys.argv[1:])
