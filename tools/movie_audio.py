"""Decode the dialogue movies' audio to 16 kHz mono WAVs for Whisper.

python tools/movie_audio.py        -> work/source/voice/movies/<movie>.wav (skips existing)
"""
import os
import sys
import time

import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import adi  # noqa: E402
import pss  # noqa: E402

OUT = os.path.join(ROOT, 'work', 'source', 'voice', 'movies')
# movies with dialogue (not: logo, test files, the opening/credits which carry songs)
MOVIES = [n for n in sorted(pss.table()) if n.startswith(('cuc_pg_', 'cuc03_', 'pg_ed', 'ham', 'qua_', 'sbk_'))]


def main():
    os.makedirs(OUT, exist_ok=True)
    for n in MOVIES:
        out = os.path.join(OUT, n[:-4] + '.wav')
        if os.path.exists(out):
            continue
        t0 = time.time()
        try:
            pcm, rate = pss.decode(n)
        except AssertionError as e:
            print(n, 'skipped:', e, flush=True)
            continue
        x = adi.to_16k_float(pcm, rate)
        adi.write_wav(out, (np.clip(x, -1, 1) * 32767).astype(np.int16), 16000)
        print(n, round(len(pcm) / rate, 1), 's', round(time.time() - t0), 's decode', flush=True)


if __name__ == '__main__':
    main()
