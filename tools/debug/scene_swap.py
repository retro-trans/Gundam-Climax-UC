"""Debug-only: copy a built ISO and make one GAME.MB scene file load another scene's data, to reach a
late-game screen quickly (e.g. the 2nd-generation name entry in place of the army select).

python tools/debug/scene_swap.py <in.iso> <out.iso> <slot entry> <content entry>
  e.g. ... v0.8.1.iso work/output/test_nameentry.iso forceselect.bin nameentry.bin
The content is read from <in.iso> (so it carries the build's patches). Never ship the output.
"""
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mb_tool  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
GAME_LBA, SECTOR = 911204, 2048


def main(src, dst, slot, content):
    t = mb_tool.read_table(os.path.join(ROOT, 'work', 'source', 'iso', 'MB', 'GAME.MB'))
    ents = sorted(t['entries'], key=lambda e: e['sector'])
    alloc = {a['name']: (b['sector'] - a['sector']) * SECTOR for a, b in zip(ents, ents[1:])}
    by = {e['name']: e for e in t['entries']}
    base = GAME_LBA * SECTOR
    shutil.copyfile(src, dst)
    with open(dst, 'r+b') as f:
        # size of the content entry as built: read from the copied table
        f.seek(base + 0x18 + by[content]['index'] * 0x30 + 36)
        size = struct.unpack('<I', f.read(4))[0]
        f.seek(base + t['data_start'] + by[content]['sector'] * SECTOR)
        data = f.read(size)
        assert len(data) <= alloc[slot], (len(data), alloc[slot])
        f.seek(base + t['data_start'] + by[slot]['sector'] * SECTOR)
        f.write(data + b'\0' * (alloc[slot] - len(data)))
        f.seek(base + 0x18 + by[slot]['index'] * 0x30 + 36)
        f.write(struct.pack('<I', len(data)))
    print('%s now holds %s (%d bytes) in %s' % (slot, content, len(data), dst))


if __name__ == '__main__':
    main(*sys.argv[1:5])
