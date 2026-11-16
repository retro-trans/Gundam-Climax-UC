# Voice subtitles

English subtitles for voiced lines that have no on-screen text: tutorial instructor lines, Chronicle
briefing voice-over, Chronicle and Progress in-mission dialogue.

## Audio
- Voices are in `MB/STREAM.MB` (6,337 `.adi` clips; entry sectors are relative to the archive's data
  start). Format: `SShd` header (type 0x10 PS-ADPCM, 24 kHz mono for voices) + `SSbd` + size + 8
  padding bytes, frames from file offset 0x30. Decoder: `tools/adi.py`.
- Clip families: `evp` 572 (Progress in-mission), `evc` 994 (Chronicle in-mission), `evt` 254
  (tutorial), `br_` 519 (briefing voice-over), `mp_` 72 (mission-intro narration; already shown as
  text), `pv_` 3,192 (battle barks, not subtitled), `sys` 225, `d_*` 348, `bgm` 47.
- Speaker code = middle part of the clip name (`evc009_sl1_ze`: sl1 = soldier, ze = faction/era).

## Transcripts
- `tools/transcribe.py` (Whisper large-v3 via faster-whisper on the GPU, separate 64-bit Python 3.11
  env in `work/bin/whisper/`) -> `work/source/voice/transcripts.jsonl`, 2,339 clips (evp, evc, evt,
  br_), with clip length and timed segments. Names are often mis-heard (カミーユ・ビダン -> 神湯ヴィラン);
  translators fix them from context and record the corrected line in `jp_fixed`.

## Translation
- `tools/voice_slices.py make` -> 12 slices of 200 clips in scene order (family, then number), with
  speaker code, trigger scripts that play the clip, and an `asr: low` mark from Whisper's confidence.
  Brief: `docs/voice_brief.md`. `merge --apply` -> `work/translation/en/subtitles.json`.
- Review stages: `tools/voice_review.py export | apply <stage> | check` (see the brief).

## Engine (`tools/subtitles.py`, patched into SLPS_256.27 by `tools/build.py`)
How a voice is played: trigger scripts (`.trg`, voice record `u16 0x0A09, u16 0x004B, u32 0x30,
char[32] clip`) in missions and the briefing command system (`okozo_cmd_voice.cpp`, sprintf
`"%s.adi"` at 0x315D88) both end in the stream-start function **0x177940(name, channel)**
(callers seen at runtime: 0x315DC8 briefing, 0x2179A8 mission trigger task, 0x318008/0x200EDC BGM).

Where the code and table live: the ELF's first load segment stored all of .bss (0x36FB00-0x4B3180,
1.3 MB of zeros) in the file, and crt0 clears that range at boot anyway. The build cuts that segment's
file size to end at 0x36FB00 and points the second program header (an empty PT_LOAD before) at the
freed file space, loading the blob at **0x4B3200**, right after the program end. The ELF file keeps its
size and disc position. crt0's SetupHeap start (0x1001D0/0x1001D8) and the libkernel `end` word
(0x31F774) move past the blob, so the C heap (which used only ~1 KB) starts after it. The game's own
heap is fixed at 0x600000-0x1F00000 (0x1A3544) and is not touched.

Hooks:
1. Entry of 0x177940: case-insensitive lookup of the clip name in the table; a hit starts that clip's
   subtitle (a clip with no text clears it).
2. Entries of two tasks that run every frame (both reached through vtables):
   0x2FCEE0 menu-scene task (briefings, menus) and 0x218DB0 mission voice-trigger task. The entry
   jumps to a wrapper that runs the whole task first (trampoline with the two replaced
   instructions) and then calls `draw_core`, so the subtitle is drawn after, i.e. on top of, what
   the task drew. Neither task reads stack-passed arguments (checked), so the wrapper's frame is
   safe. `draw_core` runs at most once per frame (COP0 Count guard), advances the subtitle clock
   (COP0 Count >> 12, 72,000 units per second, so the frame rate does not matter) and draws the
   current page.

Drawing uses the game's own text renderer: context `*(gp-0x7AB8)`, colour `0x196B90(ctx, r, g, b, a)`,
2D base matrix copied from scratchpad 0x70003F10 (`0x1396E8`), translate `0x18DDD0`, draw
`0x196D00(ctx, matrix, "%s", text)`. Screen units are 640 x 448, y = top of the glyphs. Lines are
centred, the last line's top is at y = 398, 22 units apart, at most 2 lines and 90 characters per
page; longer text is split into pages timed by text length.

Glyph budget: the renderer draws at most `ctx+0x48C` glyphs per frame (200 in missions, 400 elsewhere,
chosen at 0x1AB750; the same number sizes the glyph cache) and counts them in `ctx+0x530`. Over the
cap, glyphs are silently dropped. `draw_core` therefore picks per frame: full outline (6 passes) if
it fits, else a drop shadow (2 passes), else plain white, keeping a reserve for game text drawn
later in the frame (60 glyphs in menus, 10 in missions, where the HUD draws no text).

## Movies (Progress-mode cutscenes, endings, character events)
- MOVIE3.MB (not extracted; read from the ISO by `tools/pss.py`) holds 38 `.pss` MPEG program
  streams. Audio = private stream 1 packets, each payload with a 4-byte sub-header (ff a0 00 00);
  the first carries `SShd` (type 1 = 16-bit LE PCM, 48 kHz stereo, interleave 0x200) + `SSbd`.
  `tools/movie_audio.py` -> 16 kHz WAVs; `tools/transcribe.py --movies` (Whisper, VAD on) ->
  `work/source/voice/movie_transcripts.jsonl` with timed segments. 31 dialogue movies (cuc03_nt1
  has no audio; logo/test/opening/credits skipped), 147 segments.
- Translation: `tools/movie_slices.py make|merge` -> `subtitles.json["<movie>.pss"].cues`
  ([start, end, en], seconds). The table builder turns cues into pages; a gap over 0.15 s between
  cues blanks the subtitle.
- Engine hooks:
  - entry of 0x3181E0 (scene script "play movie", a0 = file name, e.g. `CUC_PG_CA001a.pss`):
    look the name up (path stripped, case-insensitive) -> pending record (state +16).
  - CHiMpeg state machine 0x199B00: the "Start Movie" / "Stop Movie" debug-log calls (empty
    functions) at 0x199B44 / 0x199CD8 are redirected: start moves the pending record to the
    current one, sets the movie flag (state +20) and resets the clock; stop clears it.
  - entry of the CHiMovie task 0x1F2EE0 (draws the movie frame each frame): a third draw hook.
    While the movie flag is set only this hook draws; otherwise only the other two do.
  - Draw order: the movie frame is drawn in draw list (group 0, priority 6) and game text in
    priority 5, so the subtitle text switches the text context's priority (ctx+0x4B4) to 7 while it
    draws and restores it.

## Real-hardware notes
- No file sizes change; the ELF stays at the same disc position. The blob is ordinary loaded data in
  a PT_LOAD segment (the BIOS loader handles several segments).
- Memory: blob ~0.3 MB at 0x4B3200 inside the 0x4B3180-0x600000 gap that the game never uses (zero in
  every sampled state); the C heap moves up by the blob size.
- Timing uses COP0 Count, which runs on real hardware; no busy waits, no new threads.
- Risk to check on hardware: none of the hooks touches GS/DMA directly; drawing goes through the
  game's renderer and its own per-frame cap.

## Known limits
- Battle barks (`pv_`, 3,192 clips; also the personality-select VOICE sample) are not subtitled.
- Also subtitled since 0.8.1: `s###` sortie calls and shouts (missions, opening cutscenes) and the
  `d_###` character-card quotes. Voices started by the menu sound player (0x317FA0, called only
  from the menu-scene task; return address 0x318008) get a y offset (state +24) that puts the page
  at the top of the screen, because the card screens have their description box at the bottom.
- Not subtitled: `sys` announcer lines (they repeat on-screen menu text), `demo` and `bgm` music,
  and the ending movie `end.pss` (theme song only).
- Subtitles keep their clock while the game is paused.
- The HUD's centre marker draws over the middle of the subtitle in missions.
- Lines are timed by clip length (+0.4 s), not by the stream's actual stop; skipping a voice leaves
  the subtitle up until its time runs out or the next clip starts.
