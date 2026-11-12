"""Write *.en.json copies of translation files without Japanese script text (for git).

For strings.json / cards.json / slice outputs: drops jp fields; any remaining value that
contains Japanese script (kana/kanji) is removed. Names and UI terms in the glossary are
allowed in Japanese, so glossary files are not processed.

Usage: python strip_jp.py   (processes work/translation/en/*.json and slices/out/*.json)
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JP = re.compile('[぀-ヿ㐀-鿿ｦ-ﾟ]')
DROP = {'jp', 'name_jp', 'label_jp', 'model_jp', 'desc_jp', 'desc_jp_lines'}


def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items() if k not in DROP and not (isinstance(x, str) and JP.search(x))}
    if isinstance(v, list):
        return [clean(x) for x in v if not (isinstance(x, str) and JP.search(x))]
    return v


def main():
    files = glob.glob(os.path.join(ROOT, 'work', 'translation', 'en', '*.json')) + \
        glob.glob(os.path.join(ROOT, 'work', 'translation', 'en', 'slices', 'out', '*.json'))
    n = 0
    for f in files:
        if f.endswith('.en.json'):
            continue
        out = f[:-5] + '.en.json'
        json.dump(clean(json.load(open(f, encoding='utf-8'))), open(out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        n += 1
    print('wrote', n, '.en.json files')


if __name__ == '__main__':
    main()
