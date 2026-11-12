"""Voice / music clips in STREAM.MB (*.adi): Sony PS-ADPCM.

Two layouts:
  * 'SShd' header (0x18 bytes: type 0x10 = PS-ADPCM, sample rate, channels, interleave) followed by
    'SSbd' + data size + 8 padding bytes + frames (data at file offset 0x30; found by frame-alignment
    test). Voices: 24 kHz mono. BGM: 48 kHz stereo.
  * headerless PS-ADPCM frames (evp* ...); sample rate assumed DEFAULT_RATE.
PS-ADPCM frame = 16 bytes: (predictor << 4 | shift), flags, 14 bytes = 28 4-bit samples. The loop/end
flags are ignored: streamed clips set them at every interleave block, so all frames are decoded.

python tools/adi.py list [prefix]           entries of STREAM.MB
python tools/adi.py wav <name> <out.wav>    decode one clip
"""
import os
import struct
import sys
import wave

import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import mb_tool  # noqa: E402

STREAM = os.path.join(ROOT, 'work', 'source', 'iso', 'MB', 'STREAM.MB')
DEFAULT_RATE = 24000
COEF = [(0, 0), (60, 0), (115, -52), (98, -55), (122, -60)]

_T = None
_DS = 0


def table():
    global _T, _DS
    if _T is None:
        t = mb_tool.read_table(STREAM)
        _DS = t['data_start']
        _T = {e['name']: e for e in t['entries']}
    return _T


def read(name):
    e = table()[name]
    with open(STREAM, 'rb') as f:
        f.seek(_DS + e['sector'] * 2048)   # sectors are relative to the archive's data start
        return f.read(e['size'])


def decode_mono(data):
    out = []
    h1 = h2 = 0
    for k in range(0, len(data) - 15, 16):
        b0 = data[k]
        pred, shift = (b0 >> 4) & 0xF, b0 & 0xF
        if pred > 4:
            pred = 0
        c1, c2 = COEF[pred]
        for i in range(14):
            byte = data[k + 2 + i]
            for nib in (byte & 0xF, byte >> 4):
                s = (nib << 12) & 0xFFFF
                if s & 0x8000:
                    s -= 0x10000
                s = (s >> shift) + ((h1 * c1 + h2 * c2 + 32) >> 6)
                s = max(-32768, min(32767, s))
                out.append(s)
                h2, h1 = h1, s
    return np.array(out, np.int16)


def decode(name):
    """-> (int16 samples (mono; stereo is mixed down), sample rate)."""
    d = read(name)
    if d[:4] == b'SShd':
        hs, typ, rate, ch, inter = struct.unpack_from('<5I', d, 4)
        p = 8 + hs
        assert d[p:p + 4] == b'SSbd', name
        size = struct.unpack_from('<I', d, p + 4)[0]
        body = d[p + 16:p + 8 + size]   # 'SSbd' + size + 8 padding bytes, then 16-byte ADPCM frames
        if ch == 1:
            return decode_mono(body), rate
        chans = [bytearray() for _ in range(ch)]
        for k in range(0, len(body), inter * ch):
            for c in range(ch):
                chans[c] += body[k + c * inter:k + (c + 1) * inter]
        pcm = [decode_mono(bytes(c)) for c in chans]
        n = min(len(x) for x in pcm)
        return (np.mean([x[:n].astype(np.int32) for x in pcm], axis=0)).astype(np.int16), rate
    return decode_mono(d), DEFAULT_RATE


def to_16k_float(pcm, rate):
    x = pcm.astype(np.float32) / 32768.0
    if rate == 16000:
        return x
    n = int(len(x) * 16000 / rate)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def write_wav(path, pcm, rate):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'list':
        for n, e in sorted(table().items()):
            if len(a) < 2 or n.startswith(a[1]):
                print(n, e['size'])
    elif a[0] == 'wav':
        pcm, rate = decode(a[1])
        write_wav(a[2], pcm, rate)
        print(a[2], len(pcm), 'samples @', rate, '=', round(len(pcm) / rate, 2), 's')
