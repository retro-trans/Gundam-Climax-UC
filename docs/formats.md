# File formats and disc layout

## Disc (ISO9660, files placed from LBA 900000)

| File | LBA | Size | Notes |
| --- | --- | --- | --- |
| SLPS_256.27 | 900001 | 3,879,836 | ELF, one PT_LOAD at 0x100000 (code+data+zeroed BSS to 0x4B3180) |
| MODULES/IOPRP300.IMG, IOP_IRX.EPK | 901896, 902031 | | IOP modules |
| ENVVAR/ENVVAR.LCK, MB/FILES_R.LCK | 902157, 902160 | | obfuscated small tables (not needed so far) |
| MB/TESTDATA.MB | 902161 | 18.5 MB | dev data |
| MB/GAME.MB | 911204 | 499 MB | main archive (2,415 files) |
| MB/MOVIE3.MB | 1155083 | 1.24 GB | movies |
| MB/STREAM.MB | 1760707 | 579 MB | audio streams (voice, BGM) |
| ZZ_DUMMY.BIN | 2043219 | 232 MB | padding |

Files are packed back-to-back, so the build patches in place: each GAME.MB entry may grow only
to its sector allocation (`tools/build.py` checks). The ELF has ~1.2 KB sector slack.

## MB13CDVD archive — `tools/mb_tool.py`
## FPK container (nested) — `tools/fpk_tool.py`
## XTS texture
`XTSAG\0` header; image header with data offset, size, width, height, bpp (24-bit backgrounds,
4-bit CLUT fonts). Converter: todo (needed for texture translation).

## C2B table (CSV2BIN output) — `tools/textlib.py`

```
0x00 "C2B\0"  0x04 char[32] title  0x24 char[48] struct name
0x54 u32 nfields  0x58 u32 nrecords  0x5C u32 record size
0x60 field[nfields] = { u32 type, u32 label }   type is a multichar constant: 'I4','F4','C24','C512'
records follow; several tables are concatenated in one file.
```
Field definitions are documented by the developers' own `format.csv` (in GAME.MB).
Message records (`bmes`) carry a 512-byte message field.

## Fixed-record .inf

`u32 count`, then `count` records of `(size-4)/count` bytes. String slots found generically
(`textlib.extract_fixed`). `card_info.inf` is documented in `tools/cards.py`.

## Mission intro CSV (`mp_cn_*.inf`, `mp_pr_*.inf`)

Shift-JIS CSV, CRLF. Line 0 date + title (`Ｕ.Ｃ. ００７９.１１,,,//シロー1`), line 1 English
subtitle, line 2 a number (duration?), then narration lines (`text,,,`).

## Font `s18rm04.ufm` — `tools/ufm_tool.py`, `docs/vwf.md`
