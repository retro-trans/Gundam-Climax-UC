"""Movie subtitle translation (Progress-mode cutscenes, endings, character events).

  python tools/movie_slices.py make       -> work/translation/en/voice/movies/m##.json (+ .gloss.json)
  python tools/movie_slices.py merge [--apply]
        <- work/translation/en/voice/movies/out/m##.json -> subtitles.json {"<movie>.pss": {"cues": ...}}

Slice row: {"id": "cuc_pg_ca001.pss#03", "start": 12.4, "end": 15.9, "jp": "...", "asr": "low"?}
Output rows: {"id", "en", "jp_fixed"?, "note"?, "flag"?}   (en "" = no subtitle for that segment;
             a row may also set "start"/"end" to retime it, e.g. when merging two segments)
"""
import glob
import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

SRC = os.path.join(ROOT, 'work', 'source', 'voice', 'movie_transcripts.jsonl')
MD = os.path.join(ROOT, 'work', 'translation', 'en', 'voice', 'movies')
OUTD = os.path.join(MD, 'out')
SUBS = os.path.join(ROOT, 'work', 'translation', 'en', 'subtitles.json')
MOVIES = ['cuc_pg_ca%03d' % k for k in range(1, 19)] + ['cuc_pg_ca001a', 'cuc_pg_ca004a'] +     ['pg_ed%03d' % k for k in range(1, 9)] + ['ham', 'qua_zg', 'sbk_91']
GROUPS = [('m01', tuple(MOVIES))]     # ~140 segments: one slice


def load():
    return {json.loads(l)['movie']: json.loads(l) for l in open(SRC, encoding='utf-8')}


def make():
    mv = load()
    os.makedirs(OUTD, exist_ok=True)
    import slice_gloss
    E = slice_gloss.entries()
    for name, movies in GROUPS:
        rows = []
        for m in movies:
            rec = mv.get(m + '.pss')
            if not rec:
                print('missing', m)
                continue
            for k, seg in enumerate(rec['segments']):
                a, b, text, lp, ns = seg
                r = {'id': '%s#%02d' % (rec['movie'], k), 'start': a, 'end': b, 'jp': text}
                if lp < -0.7 or ns > 0.6:
                    r['asr'] = 'low'
                rows.append(r)
        json.dump({'slice': name, 'movies': list(movies), 'rows': rows},
                  open(os.path.join(MD, name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        t = '\n'.join(r['jp'] for r in rows)
        hits = [c for keys, c in E if any(k in t for k in keys)]
        json.dump(hits, open(os.path.join(MD, name + '.gloss.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=0)
        print(name, len(rows), 'segments')


def merge(apply):
    mv = load()
    subs = json.load(open(SUBS, encoding='utf-8'))
    seg = {}
    for m, rec in mv.items():
        for k, s in enumerate(rec['segments']):
            seg['%s#%02d' % (m, k)] = s
    cues = {}
    n = flagged = 0
    for f in sorted(glob.glob(os.path.join(OUTD, 'm*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        for r in d['rows']:
            m = r['id'].split('#')[0]
            s = seg.get(r['id'])
            if s is None:
                print('unknown segment', r['id'])
                continue
            cues.setdefault(m, [])
            if not r.get('en'):
                flagged += 1
                continue
            cues[m].append([r.get('start', s[0]), r.get('end', s[1]), r['en']])
            n += 1
    for m, c in sorted(cues.items()):
        row = subs.get(m, {})
        row.update({'cues': sorted(c), 'status': 'translated'})
        subs[m] = row
    print('movies %d, cues %d, empty %d%s' % (len(cues), n, flagged, '' if apply else ' (dry run)'))
    if apply:
        json.dump(dict(sorted(subs.items())), open(SUBS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'make':
        make()
    elif a[0] == 'merge':
        merge('--apply' in a)
