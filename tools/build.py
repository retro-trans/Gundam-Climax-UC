"""Build the English patch ISO by patching a copy of the original ISO in place.

Every file keeps its LBA. GAME.MB entries keep their sector; a replaced entry may grow
only up to its sector allocation (the gap to the next entry). The entry's size field in
the GAME.MB header is updated. Real-hardware note: nothing here changes disc layout.

Usage: python build.py <version> [--no-copy]
  writes work/output/Gundam_Climax_UC_EN_v<version>.iso
"""
import os
import shutil
import struct
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import mb_tool  # noqa: E402
import vwf  # noqa: E402
import elf_text  # noqa: E402
import textenc  # noqa: E402
import json  # noqa: E402

SRC_ISO = os.path.join(ROOT, 'Mobile Suit Gundam - Climax U.C. (Japan).iso')
SRC = os.path.join(ROOT, 'work', 'source')
OUT = os.path.join(ROOT, 'work', 'output')
BUILD = os.path.join(ROOT, 'work', 'build')
SECTOR = 2048

LBA = {
    'SLPS_256.27': 900001,
    'GAME.MB': 911204,
}
ELF_SIZE = 3879836
ELF_BASE, ELF_FOFF = 0x100000, 0x80


def elf_patches():
    """list of (vaddr, bytes)"""
    return [(vwf.HALFWIDTH_FN, vwf.halfwidth_patch())]


def game_mb_files():
    """{entry name: new bytes} for GAME.MB."""
    files = {}
    font, _ = vwf.build_font(os.path.join(SRC, 'game', 's18rm04.ufm'))
    files['s18rm04.ufm'] = font
    # text inserters register here
    try:
        import insert_text
        files.update(insert_text.build_all())
    except ImportError:
        pass
    # translated textures (work/translation/en/textures.json), patched into every copy
    import tex_make
    rep = []
    tex_make.apply(files, rep)
    import save_title
    save_title.apply(files, rep)
    open(os.path.join(BUILD, 'tex_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
    print('textures: %d files, %d problems' % (sum(1 for r in rep if r.startswith('TEX ') and 'copies' in r),
                                              sum(1 for r in rep if 'not found' in r)))
    return files


def main():
    ver = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(BUILD, exist_ok=True)
    out = os.path.join(OUT, 'Gundam_Climax_UC_EN_v%s.iso' % ver)
    elf_only = '--elf-only' in sys.argv      # rewrite only the executable inside an existing build
    if (not elf_only and '--no-copy' not in sys.argv) or not os.path.exists(out):
        t0 = time.time()
        shutil.copyfile(SRC_ISO, out)
        print('copied ISO in %.0fs' % (time.time() - t0))

    with open(out, 'r+b') as iso:
        # --- ELF
        elf = bytearray(open(os.path.join(SRC, 'iso', 'SLPS_256.27'), 'rb').read())
        for va, code in elf_patches():
            o = va - ELF_BASE + ELF_FOFF
            elf[o:o + len(code)] = code
        # player-facing executable text (in place, or relocated into dead debug strings)
        rows = json.load(open(os.path.join(ROOT, 'work', 'translation', 'en', 'strings.json'), encoding='utf-8'))
        tr = {r['jp']: r['en'] for r in rows if r.get('en') and any('addr' in o and 'path' not in o for o in r['occ'])}
        rep = elf_text.apply(elf, tr, textenc.encode)
        open(os.path.join(BUILD, 'elf_text_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
        print('ELF text: %d translated, %s' % (len(tr), rep[-1]))
        # voice subtitles: hook code + clip table, loaded from the freed .bss file image (docs/subtitles.md)
        import subtitles
        blob, labels, sprobs, nclips = subtitles.build_blob()
        srep = subtitles.patch_elf(elf, blob, labels)
        open(os.path.join(BUILD, 'subtitles_report.txt'), 'w', encoding='utf-8').write(
            '\n'.join(srep + sprobs) + '\n')
        print('%s, %d clips, %d problems' % (srep[0], nclips, len(sprobs)))
        assert len(elf) == ELF_SIZE
        iso.seek(LBA['SLPS_256.27'] * SECTOR)
        iso.write(elf)
        open(os.path.join(BUILD, 'SLPS_256.27'), 'wb').write(elf)

        if elf_only:
            print('ELF only: GAME.MB left as built')
            return
        # --- GAME.MB
        t = mb_tool.read_table(os.path.join(SRC, 'iso', 'MB', 'GAME.MB'))
        ents = sorted(t['entries'], key=lambda e: e['sector'])
        alloc = {}
        for a, b in zip(ents, ents[1:]):
            alloc[a['name']] = (b['sector'] - a['sector']) * SECTOR
        alloc[ents[-1]['name']] = 499464192 - t['data_start'] - ents[-1]['sector'] * SECTOR
        byname = {e['name']: e for e in t['entries']}
        base = LBA['GAME.MB'] * SECTOR
        report = []
        for name, data in sorted(game_mb_files().items()):
            e = byname[name]
            if len(data) > alloc[name]:
                raise SystemExit('%s: %d bytes > allocation %d' % (name, len(data), alloc[name]))
            iso.seek(base + t['data_start'] + e['sector'] * SECTOR)
            iso.write(data + b'\0' * (((len(data) + SECTOR - 1) // SECTOR * SECTOR) - len(data)))
            iso.seek(base + 0x18 + e['index'] * 0x30 + 36)
            iso.write(struct.pack('<I', len(data)))
            report.append('%s %d/%d' % (name, len(data), alloc[name]))
        print('GAME.MB replaced:', len(report))
        for r in report:
            print('  ' + r)
    print('built', out)


if __name__ == '__main__':
    main()
