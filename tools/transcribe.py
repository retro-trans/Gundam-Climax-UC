"""Transcribe voice clips from STREAM.MB with Whisper (faster-whisper, GPU).

Runs in the separate 64-bit Python 3.11 environment (the project's Python is 32-bit):
    work/bin/whisper/venv311/Scripts/python.exe tools/transcribe.py <prefix> [prefix ...] [--model large-v3]

Output: work/source/voice/transcripts.jsonl (Japanese; work/source is git-ignored), one line per clip:
    {"clip", "seconds", "text", "segments": [[start, end, text]], "avg_logprob", "no_speech"}
Clips already in the file are skipped, so the run can be resumed.
Model cache: work/bin/whisper/hf (Systran/faster-whisper-<model> from Hugging Face).
"""
import glob
import json
import os
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
os.environ.setdefault('HF_HOME', os.path.join(ROOT, 'work', 'bin', 'whisper', 'hf'))
site = os.path.join(os.path.dirname(sys.executable), '..', 'Lib', 'site-packages', 'nvidia')
for d in glob.glob(os.path.join(site, '*', 'bin')):
    os.add_dll_directory(os.path.abspath(d))
    os.environ['PATH'] = os.path.abspath(d) + os.pathsep + os.environ['PATH']

import adi  # noqa: E402

OUT = os.path.join(ROOT, 'work', 'source', 'voice', 'transcripts.jsonl')


def main(prefixes, model_name='large-v3'):
    from faster_whisper import WhisperModel
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding='utf-8'):
            done.add(json.loads(line)['clip'])
    clips = sorted(n for n in adi.table() if n.startswith(tuple(prefixes)) and n not in done)
    print(len(clips), 'clips to do', flush=True)
    model = WhisperModel(model_name, device='cuda', compute_type='float16')
    t0 = time.time()
    with open(OUT, 'a', encoding='utf-8') as f:
        for k, n in enumerate(clips):
            pcm, rate = adi.decode(n)
            audio = adi.to_16k_float(pcm, rate)
            segs, info = model.transcribe(audio, language='ja', beam_size=5, vad_filter=False,
                                          condition_on_previous_text=False, temperature=0.0)
            segs = list(segs)
            rec = {'clip': n, 'seconds': round(len(pcm) / rate, 2),
                   'text': ''.join(s.text for s in segs).strip(),
                   'segments': [[round(s.start, 2), round(s.end, 2), s.text.strip()] for s in segs],
                   'avg_logprob': round(sum(s.avg_logprob for s in segs) / len(segs), 3) if segs else None,
                   'no_speech': round(max((s.no_speech_prob for s in segs), default=1.0), 3)}
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            f.flush()
            if k % 25 == 0:
                print('%d/%d %.0fs %s %s' % (k, len(clips), time.time() - t0, n, rec['text'][:30]), flush=True)
    print('done in %.0fs' % (time.time() - t0))


MOVIE_WAVS = os.path.join(ROOT, 'work', 'source', 'voice', 'movies')
MOVIE_OUT = os.path.join(ROOT, 'work', 'source', 'voice', 'movie_transcripts.jsonl')


def movies(model_name='large-v3'):
    """Movie dialogue (16 kHz WAVs from tools/movie_audio.py) -> movie_transcripts.jsonl, one line per
    movie with timed segments (VAD on: the movies have long silent stretches)."""
    import wave
    import numpy as np
    from faster_whisper import WhisperModel
    done = set()
    if os.path.exists(MOVIE_OUT):
        for line in open(MOVIE_OUT, encoding='utf-8'):
            done.add(json.loads(line)['movie'])
    wavs = sorted(f for f in glob.glob(os.path.join(MOVIE_WAVS, '*.wav'))
                  if os.path.basename(f)[:-4] + '.pss' not in done)
    print(len(wavs), 'movies to do', flush=True)
    model = WhisperModel(model_name, device='cuda', compute_type='float16')
    with open(MOVIE_OUT, 'a', encoding='utf-8') as f:
        for fn in wavs:
            w = wave.open(fn)
            audio = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768.0
            segs, info = model.transcribe(audio, language='ja', beam_size=5, vad_filter=True,
                                          condition_on_previous_text=False, temperature=0.0)
            segs = list(segs)
            rec = {'movie': os.path.basename(fn)[:-4] + '.pss', 'seconds': round(len(audio) / 16000, 2),
                   'segments': [[round(s.start, 2), round(s.end, 2), s.text.strip(), round(s.avg_logprob, 3),
                                 round(s.no_speech_prob, 3)] for s in segs]}
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            f.flush()
            print(rec['movie'], len(segs), 'segments', flush=True)


if __name__ == '__main__':
    if '--movies' in sys.argv:
        movies()
        sys.exit(0)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    model = 'large-v3'
    if '--model' in sys.argv:
        model = sys.argv[sys.argv.index('--model') + 1]
        args.remove(model)
    main(args, model)
