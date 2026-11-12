"""Coverage check: Japanese text left in a built ISO's GAME.MB, per file, vs the original.

Usage: python coverage.py <built.iso> [out.txt]
Every remaining string must be either untranslated-on-purpose (listed in docs) or a bug.
"""
import collections
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import textlib  # noqa: E402

GAME_MB_LBA = 911204


def count(it):
    c = collections.Counter()
    left = collections.defaultdict(list)
    for path, data in it:
        try:
            occ = textlib.extract_file(path, data)
        except Exception:  # noqa
            continue
        for o in occ:
            if 'max' in o and o['max'] < len(o['jp'].encode('cp932')):
                continue
            c[path] += 1
            left[path].append(o['jp'])
    return c, left


def main():
    iso = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(textlib.ROOT, 'work', 'build', 'coverage.txt')
    orig, _ = count(textlib.iter_mb_files())
    built, left = count(textlib.iter_mb_files(iso, GAME_MB_LBA * 2048))
    with open(out, 'w', encoding='utf-8') as f:
        for p in sorted(set(orig) | set(built)):
            if built.get(p):
                f.write('%5d / %5d  %s\n' % (built[p], orig.get(p, 0), p))
                for s in left[p][:5]:
                    f.write('        %s\n' % s.replace('\n', '\n'))
    print('original strings %d, left in build %d (%.1f%%) -> %s' % (
        sum(orig.values()), sum(built.values()), 100.0 * sum(built.values()) / max(1, sum(orig.values())), out))


if __name__ == '__main__':
    main()
