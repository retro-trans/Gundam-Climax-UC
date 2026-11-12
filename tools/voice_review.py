"""Review stages for voice subtitles (accuracy -> editorial -> proofread, BASE_RULES).

  python tools/voice_review.py export [parts]        -> work/translation/en/voice/review/vr<N>.txt
  python tools/voice_review.py apply <stage> [--apply]
        <- work/translation/en/voice/review/out/<stage>_vr<N>.json  (dry run without --apply)
  python tools/voice_review.py check                 mechanical proofreading checks (ASCII, length,
                                                      reading speed, doubled words, page fit)

Line format in the export (scene order):
  evc009_sl1_ze.adi | 2.3s | sl1 | JP: <transcript (or corrected jp_fixed)> | EN: <subtitle>
Output: {"stage", "part", "rows_examined", "edits": [{"id", "en", "reason"}],
         "returned": [{"id", "to", "why"}], "uncertain": [...]}
"""
import glob
import json
import os
import re
import shutil
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import voice_slices  # noqa: E402

SUBS = voice_slices.SUBS
RD = os.path.join(voice_slices.VD, 'review')
OUTD = os.path.join(RD, 'out')
APPLIED = os.path.join(OUTD, 'applied')


def rows_in_order():
    rows = [json.loads(l) for l in open(voice_slices.TRANS, encoding='utf-8')]
    rows.sort(key=lambda r: voice_slices.key(r['clip']))
    return rows


def export(parts=6):
    subs = json.load(open(SUBS, encoding='utf-8'))
    rows = [r for r in rows_in_order() if r['clip'] in subs]
    os.makedirs(OUTD, exist_ok=True)
    per = -(-len(rows) // parts)
    for k in range(parts):
        chunk = rows[k * per:(k + 1) * per]
        out = []
        for r in chunk:
            s = subs[r['clip']]
            parts_ = r['clip'][:-4].split('_')
            spk = '' if r['clip'].startswith('br_') else (parts_[1] if len(parts_) > 1 else '')
            jp = s.get('jp_fixed') or r['text']
            en = s.get('en', '')
            en = ' // '.join(en) if isinstance(en, list) else en
            out.append('%s | %.1fs | %s | JP: %s | EN: %s' % (r['clip'], r['seconds'], spk, jp, en))
        fn = os.path.join(RD, 'vr%d.txt' % (k + 1))
        open(fn, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
        print(os.path.basename(fn), len(out))


def apply(stage, do_apply):
    subs = json.load(open(SUBS, encoding='utf-8'))
    files = sorted(glob.glob(os.path.join(OUTD, '%s_vr*.json' % stage)))
    n = 0
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        for e in d.get('edits', []):
            cid = e['id']
            if cid not in subs:
                print('  unknown clip', cid)
                continue
            old = subs[cid].get('en')
            if old == e['en']:
                continue
            if n < 12 or not do_apply:
                print('  %s\n    - %s\n    + %s   (%s)' % (cid, old, e['en'], e.get('reason', '')))
            if do_apply:
                h = subs[cid].setdefault('history', [])
                h.append({'stage': stage, 'old': old, 'reason': e.get('reason', '')})
                subs[cid]['en'] = e['en']
                subs[cid]['status'] = stage
            n += 1
        for r in d.get('returned', []):
            print('  returned %s -> %s: %s' % (r.get('id'), r.get('to'), r.get('why')))
    print('%s: %d edits from %d files%s' % (stage, n, len(files), '' if do_apply else ' (dry run)'))
    if do_apply:
        json.dump(dict(sorted(subs.items())), open(SUBS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.makedirs(APPLIED, exist_ok=True)
        for f in files:
            shutil.move(f, os.path.join(APPLIED, os.path.basename(f)))


def check():
    import subtitles
    import textenc
    subs = json.load(open(SUBS, encoding='utf-8'))
    timing = subtitles.load_timing()
    probs = []
    for cid, s in sorted(subs.items()):
        en = s.get('en') or ''
        texts = en if isinstance(en, list) else [en]
        for t in texts:
            if any(ord(c) > 126 for c in t):
                probs.append('%s non-ASCII: %s' % (cid, t))
            if re.search(r'\b(\w+) \1\b', t, re.I):
                probs.append('%s doubled word: %s' % (cid, t))
            if '  ' in t or t != t.strip():
                probs.append('%s spacing: %r' % (cid, t))
        sec = timing.get(cid.lower(), {}).get('seconds', 0)
        chars = len(' '.join(texts))
        if sec and chars / max(sec, 1.0) > 22:
            probs.append('%s fast: %d chars in %.1fs' % (cid, chars, sec))
    p2 = []
    subtitles.build_data(0, subs, timing, p2)
    for p in probs + p2:
        print(p)
    print('%d problems' % (len(probs) + len(p2)))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'export':
        export(int(a[1]) if len(a) > 1 else 6)
    elif a[0] == 'apply':
        apply(a[1], '--apply' in a)
    elif a[0] == 'check':
        check()
