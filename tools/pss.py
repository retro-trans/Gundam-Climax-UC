"""Movies in MOVIE3.MB (*.pss, PS2 MPEG program stream): extract, and pull the audio out.

PSS audio is MPEG-PS private stream 1 (0xBD). The first audio packet starts with an 'SShd' header
(type, rate, channels, interleave) and 'SSbd' + size; the payload is 16-bit little-endian PCM (type 1,
as in this game's movies: 48 kHz stereo, interleave 0x200) or PS-ADPCM (type 0x10), interleaved per
channel in blocks of `interleave` bytes. Each private-stream packet payload starts with a 4-byte
sub-header (ff a0 00 00) that is stripped.

python tools/pss.py list
python tools/pss.py extract <name> <out.pss>
python tools/pss.py wav <name> <out.wav>          decode the audio track (mono mix)
python tools/pss.py info <name>
"""
import os
import struct
import sys

import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import adi  # noqa: E402

ISO = os.path.join(ROOT, 'Mobile Suit Gundam - Climax U.C. (Japan).iso')
MOVIE_LBA = 1155083
SECTOR = 2048


def table():
    with open(ISO, 'rb') as f:
        f.seek(MOVIE_LBA * SECTOR)
        head = f.read(0x18)
        assert head[:8] == b'MB13CDVD'
        count, end, ds = struct.unpack_from('<3I', head, 8)
        tab = f.read(count * 0x30)
    out = {}
    for i in range(count):
        name = tab[i * 0x30:i * 0x30 + 32].split(b'\0')[0].decode()
        sec, size = struct.unpack_from('<2I', tab, i * 0x30 + 32)
        out[name] = (MOVIE_LBA * SECTOR + ds + sec * SECTOR, size)
    return out


def read(name):
    off, size = table()[name]
    with open(ISO, 'rb') as f:
        f.seek(off)
        return f.read(size)


def audio_payload(d):
    """Concatenate the payloads of private-stream-1 packets (audio)."""
    out = bytearray()
    i = 0
    n = len(d)
    while i < n - 4:
        if d[i:i + 3] != b'\x00\x00\x01':
            i += 1
            continue
        sid = d[i + 3]
        if sid == 0xBA:                       # pack header (MPEG-2)
            stuff = d[i + 13] & 7
            i += 14 + stuff
            continue
        if sid == 0xB9:
            break
        if sid < 0xBB:
            i += 1
            continue
        plen = struct.unpack_from('>H', d, i + 4)[0]
        if sid == 0xBD:
            hlen = d[i + 8]
            p = i + 9 + hlen
            # PSS private stream 1: each payload starts with a 4-byte sub-header (ff a0 00 00)
            out += d[p + 4:i + 6 + plen]
        i += 6 + plen
    return bytes(out)


def info(name):
    d = read(name)
    a = audio_payload(d)
    k = a.find(b'SShd')
    print(name, 'size', len(d), 'audio bytes', len(a), 'SShd at', k)
    if k >= 0:
        hs, typ, rate, ch, inter = struct.unpack_from('<5I', a, k + 4)
        print(' header size', hs, 'type', typ, 'rate', rate, 'channels', ch, 'interleave', hex(inter))
        print(' head bytes', a[max(0, k - 8):k + 48].hex())
    return d, a


def decode(name):
    d = read(name)
    a = audio_payload(d)
    k = a.find(b'SShd')
    assert k >= 0, 'no SShd'
    hs, typ, rate, ch, inter = struct.unpack_from('<5I', a, k + 4)
    p = k + 8 + hs
    assert a[p:p + 4] == b'SSbd', a[p:p + 16]
    body = a[p + 8:]
    chans = [bytearray() for _ in range(ch)]
    for j in range(0, len(body) - inter * ch + 1, inter * ch):
        for c in range(ch):
            chans[c] += body[j + c * inter:j + (c + 1) * inter]
    if typ == 0x10:                           # PS-ADPCM (as in STREAM.MB voices)
        pcm = [adi.decode_mono(bytes(c)) for c in chans]
    else:
        pcm = [np.frombuffer(bytes(c[:len(c) // 2 * 2]), '<i2') for c in chans]
    m = min(len(x) for x in pcm)
    mix = np.mean([x[:m].astype(np.int32) for x in pcm], axis=0).astype(np.int16)
    return mix, rate


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'list':
        for n, (o, s) in table().items():
            print(n, s)
    elif a[0] == 'extract':
        open(a[2], 'wb').write(read(a[1]))
    elif a[0] == 'info':
        info(a[1])
    elif a[0] == 'wav':
        pcm, rate = decode(a[1])
        adi.write_wav(a[2], pcm, rate)
        print(a[2], round(len(pcm) / rate, 2), 's @', rate)
