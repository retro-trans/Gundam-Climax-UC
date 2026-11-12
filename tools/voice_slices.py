"""Voice subtitle translation slices (Whisper transcripts -> English subtitles).

  python tools/voice_slices.py make       -> work/translation/en/voice/slices/v##.json (+ .gloss.json)
  python tools/voice_slices.py merge      <- work/translation/en/voice/slices/out/v##.json
                                           -> work/translation/en/subtitles.json
  python tools/voice_slices.py status

Slice row: {"id": clip, "jp": transcript, "sec": length, "speaker": code, "missions": [trg codes],
            "asr": "low" when Whisper was unsure}
Output:    {"slice", "rows_in_slice", "rows_examined",
            "rows": [{"id", "en", "jp_fixed"?, "note"?, "flag"?}], "speakers": {code: name},
            "decisions": [...], "uncertain": [...]}
"""
import glob
import json
import os
import re
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import mb_tool  # noqa: E402

TRANS = os.path.join(ROOT, 'work', 'source', 'voice', 'transcripts.jsonl')
VD = os.path.join(ROOT, 'work', 'translation', 'en', 'voice')
SL = os.path.join(VD, 'slices')
OUTD = os.path.join(SL, 'out')
SUBS = os.path.join(ROOT, 'work', 'translation', 'en', 'subtitles.json')
GAME_MB = os.path.join(ROOT, 'work', 'source', 'iso', 'MB', 'GAME.MB')
FAMILY_ORDER = ('evt', 'br_', 'evc', 'evp')
PER_SLICE = 200


def clip_missions():
    """clip (lower) -> [trigger script codes that play it]."""
    t = mb_tool.read_table(GAME_MB)
    out = {}
    with open(GAME_MB, 'rb') as f:
        for e in t['entries']:
            if not e['name'].endswith('.trg'):
                continue
            f.seek(t['data_start'] + e['sector'] * 2048)
            d = f.read(e['size'])
            for m in re.finditer(rb'[A-Za-z0-9_]+\.adi', d):
                out.setdefault(m.group().decode().lower(), []).append(e['name'][:-8])
    return out


def key(clip):
    fam = clip[:3]
    m = re.match(r'(?:br_c(\d+)_(\d+)|ev[a-z](\d+))', clip)
    nums = tuple(int(x) for x in m.groups() if x) if m else (0,)
    return (FAMILY_ORDER.index(fam) if fam in FAMILY_ORDER else 9, nums, clip)


def make():
    rows = [json.loads(l) for l in open(TRANS, encoding='utf-8')]
    rows.sort(key=lambda r: key(r['clip']))
    mis = clip_missions()
    os.makedirs(OUTD, exist_ok=True)
    out = []
    for r in rows:
        c = r['clip']
        parts = c[:-4].split('_')
        x = {'id': c, 'jp': r['text'], 'sec': r['seconds'],
             'speaker': '' if c.startswith('br_') else (parts[1] if len(parts) > 1 else '')}
        if mis.get(c):
            x['missions'] = sorted(set(mis[c]))
        if (r.get('avg_logprob') or 0) < -0.6 or (r.get('no_speech') or 0) > 0.6:
            x['asr'] = 'low'
        out.append(x)
    names = []
    for k in range(0, len(out), PER_SLICE):
        n = 'v%02d' % (k // PER_SLICE + 1)
        names.append(n)
        json.dump({'slice': n, 'rows': out[k:k + PER_SLICE]},
                  open(os.path.join(SL, n + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    json.dump(names, open(os.path.join(SL, 'index.json'), 'w'))
    # glossary excerpts (names written correctly in the transcript; misheard ones need context)
    import slice_gloss
    E = slice_gloss.entries()
    for n in names:
        d = json.load(open(os.path.join(SL, n + '.json'), encoding='utf-8'))
        t = '\n'.join(r['jp'] for r in d['rows'])
        hits = [c for keys, c in E if any(k in t for k in keys)]
        json.dump(hits, open(os.path.join(SL, n + '.gloss.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=0)
    print('%d clips -> %d slices' % (len(out), len(names)))


def merge(dry=False):
    subs = json.load(open(SUBS, encoding='utf-8')) if os.path.exists(SUBS) else {}
    n_new = n_flag = 0
    for f in sorted(glob.glob(os.path.join(OUTD, 'v*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        for r in d['rows']:
            if r.get('flag') or not r.get('en'):
                n_flag += 1
                continue
            row = subs.get(r['id'], {})
            row.update({'en': r['en'], 'status': 'translated', 'slice': d['slice']})
            if r.get('jp_fixed'):
                row['jp_fixed'] = r['jp_fixed']
            if r.get('note'):
                row['note'] = r['note']
            subs[r['id']] = row
            n_new += 1
    print('merged %d rows, %d flagged/empty%s' % (n_new, n_flag, ' (dry run)' if dry else ''))
    if not dry:
        json.dump(dict(sorted(subs.items())), open(SUBS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def status():
    idx = json.load(open(os.path.join(SL, 'index.json')))
    for n in idx:
        o = os.path.join(OUTD, n + '.json')
        print(n, 'done' if os.path.exists(o) else '-')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'make':
        make()
    elif a[0] == 'merge':
        merge(dry='--apply' not in a)
    elif a[0] == 'status':
        status()
