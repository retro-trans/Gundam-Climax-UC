# Changelog

## 0.8.1 — 2026-11-16 (local build)

Output: `work/output/Gundam_Climax_UC_EN_v0.8.1.iso` (SHA-1 d05ab4de6457605798694b5c6eeb4a8a4c53efe7).

From player QA on 0.8.0.

### Name entry (Progress mode, 2nd-generation character)
- The kana keyboard is now English: A-Z, a-z and - . ' ! ? & , on the same keys (the keyboard table
  in `nameentry.bin` / `nameentry.pack.fpk` and the two key images). Names are entered as ASCII and
  drawn with the variable-width font. Every key and empty cell keeps its place, so cursor movement
  is unchanged. `tools/name_entry.py`.
- Checked in game by loading the name-entry scene in a debug image (typing, backspace); confirming a
  name in a real 2nd-generation playthrough is not tested.

### Voice subtitles
- 422 more clips: in-mission sortie calls and shouts (`s###`, e.g. "Amuro, Gundam, launching!") and
  the character-card voice quotes in the card gallery (`d_###`). Translated (slices v13-v14) and
  reviewed (accuracy, editorial, proofreading: 17 edits). Quotes played from the card gallery (the
  menu sound player, caller 0x318008) are drawn at the top of the screen, clear of the card
  description; mission and cutscene lines stay at the bottom. Checked in game: the card quote
  "This thing... it moves!" and the launch call in Chronicle stage 1's opening cutscene.

### Builds
- 0.8.0 ISO kept as its patch; 0.8.1 patch `work/output/patches/Gundam_Climax_UC_EN_v0.8.1.xdelta`
  (decode verified). Debug: `tools/debug/scene_swap.py` makes a test image that opens a late-game
  scene in place of another (used for the name-entry test, never shipped).

### Investigated, not changed
- Chronicle ending video (`end.pss`): its audio is the ending theme song only, no dialogue. Song lyrics
  are not subtitled. The staff roll shown with it (`staff_roll.bin`) lists Japanese staff names.

## 0.8.0 — 2026-11-12 (first public release)

Output: `work/output/Gundam_Climax_UC_EN_v0.8.0.iso` (SHA-1 791b3df19d5da71c2018e0f74634bfb05fe174a5).

Developed locally as 0.1.6; the version jumps to 0.8.0 for the first public release. Everything below
is new since 0.1.5.

### Title screen
- Version and project credit ("v0.8.0", "github.com / retro-trans") in the bottom-right corner of the
  PRESS START screen, above the copyright line. Drawn into the title background (keeping its palette;
  1,621 pixels change); the version comes from the build command. The title menu uses a different
  background, so the credit shows on the title screen only. Checked in game.

### Voice subtitles (new)
- English subtitles for 2,324 voiced lines with no on-screen text: tutorial instructors (evt),
  Chronicle briefing voice-over (br_), Chronicle and Progress in-mission dialogue (evc, evp).
  15 clips with no speech (breathing, Whisper hallucinations) have none.
- Engine (`tools/subtitles.py`, details in `docs/subtitles.md`): a hook on the stream-start function
  0x177940 looks up the clip name; hooks on the menu-scene task (0x2FCEE0) and the mission
  voice-trigger task (0x218DB0) draw the current page every frame with the game's own font renderer
  (centred, 1-2 lines, outline or drop shadow chosen from the renderer's per-frame glyph budget).
  The draw hooks wrap the tasks and draw after them, so full-screen pictures drawn by the task do
  not cover the subtitle.
  Timing uses the COP0 cycle counter, pages are timed by text length.
- Code and table (~240 KB) load from the .bss image the ELF already stored as zeros: the first
  segment's file size now ends at .bss, the second (formerly empty) program header loads the blob at
  0x4B3200, and the C heap start moves past it. ELF file size and disc position are unchanged.
- Translation: 12 slices from Whisper transcripts with mis-heard names fixed from context
  (`tools/voice_slices.py`, `docs/voice_brief.md`), then accuracy (22 edits), editorial (124) and
  proofreading (11) passes (`tools/voice_review.py`). 隊長 addressed to the unit leader = "Commander".
- Verified in game: tutorial briefing and mission (Kamille); Chronicle Amuro stage 1 briefing and
  mission; Progress stage 1 briefing (4-page line) and mission. The pause screen hides the subtitle
  (the mission task stops while paused).
- Movie subtitles: the Progress-mode cutscenes (`cuc_pg_ca001`-`018`, `001a`, `004a`), the eight
  Progress endings (`pg_ed001`-`008`) and three character events (`ham`, `qua_zg`, `sbk_91`) are
  subtitled: 144 timed lines in 30 movies. Audio pulled from the PSS streams (`tools/pss.py`,
  `tools/movie_audio.py`), transcribed with Whisper (`transcribe.py --movies`), translated
  (`tools/movie_slices.py`) and reviewed (accuracy, editorial, proofread: 5 edits). Engine: hooks
  on the scene "play movie" request (0x3181E0), CHiMpeg Start/Stop (0x199B44 / 0x199CD8) and the
  movie task (0x1F2EE0); the text switches to draw priority 7 so it lands above the movie frame
  (priority 6). Verified in game on the first Progress cutscene (Ellen's introduction).
- Battle barks (`pv_`, incl. the personality-select VOICE sample) are not subtitled by design.

### Tools
- `tools/build.py <ver> --elf-only` rewrites only the executable in an existing build.
- Debug: `gdbg.py tracestr`, `Dbg.trace_str`, `Dbg.flush_rec`, `tools/debug/stackwalk.py`,
  `tools/debug/subtest.py`; notes on PCSX2's recompiler ignoring some runtime code patches
  (`docs/debug_tools.md`).
- `.gitignore`: review `.txt` exports (they contain Japanese) are ignored.

### Title menu
- The mode descriptions under the menu ring were drawn 1:1 with the game font, but the game shows
  that 256x64 texture stretched 2x horizontally, so the text looked wide and flattened. They are
  now drawn like the original art: a smooth font (Noto Sans JP, SIL OFL) laid out at screen
  proportions and reduced to half width, small "< Mode >" header and a larger description line.
  Checked in game (Chronicle, Progress).

### MS skill names
- The 36 MS skill plates (skill select, pause STATUS, result screens) now use the game's own English
  names from the MS-select weapon panel (`unitweapon.fpk` `wp_*.xts`, last row), so both screens
  agree: e.g. Limit Disarm, Maneuverability, Invincible, Thrust, Transformation, High Speed Mode,
  Torimochi Launcher (23 names changed). Spelling slips in the panel were not copied: Chain Mine,
  Claw Missile, I.F. Attack. "Electromagnetic Wire" is "Electromag. Wire" on the plate (too wide).
  Checked in game: Gundam [G] panel and skill select both read "Limit Disarm".

### Also checked in game (0.1.5 work)
- Battle pause STATUS: stats, passive plates and MS skill plate all English.
- Progress pilot creation: army select, personality select, Abilities Introduction (stat labels,
  rank plate "Master Sergeant", HOT-BLOOD, E.F.S.F.).
- Not reached: ABILITIES SETTING (needs a finished Progress mission).

### Known issues
- Chronicle stage select and MS select: series title logos are still Japanese textures
  (`docs/textures.md`).
- Pilot name: original English plate on the tutorial pilot select reads "Kamna Tachibana"; the text
  and the Progress name use the glossary's "Kamuna".
- Subtitles keep running while the game is paused; the mission HUD's centre marker draws over them.
- A few 1-second clips read fast (up to ~30 characters per second).

### Builds
- 0.1.5 kept as `work/output/patches/Gundam_Climax_UC_EN_v0.1.5.xdelta` (decode verified).
- Local 0.1.6 (same content without the title credit) kept as
  `work/output/patches/Gundam_Climax_UC_EN_v0.1.6.xdelta` (decode verified).
- 0.8.0 patch `work/output/patches/Gundam_Climax_UC_EN_v0.8.0.xdelta`, published as
  `GundamClimaxUC-English-v0.8.0.xdelta` (decode verified). Boot-tested.

### Tools
- `tools/restore_work.py`: recreates the local working files (which hold Japanese text) from your
  disc and the committed `*.en.json` copies; subtitles store each clip's length so a fresh clone
  builds without the local transcripts.
- `tools/social_preview.py`: the GitHub social preview, composed from the game's title art.
- `xts_tool.encode_keep_palette`: edit an 8/4-bit image without re-quantizing it.

## 0.1.5 — 2026-11-11 (local build, not released)

Output: `work/output/Gundam_Climax_UC_EN_v0.1.5.iso` (SHA-1 93127f521c1274d8d3e1aa8681ff8ff519702ac9).

### Textures
- Texture copies are now found by image content (name + pixels + CLUT), in FPKs and as stand-alone
  GAME.MB files: the battle pause screen's own skill plates (97 `pause_*.xts`) are now translated.
  148 images -> 694 files in FPKs + 97 stand-alone files.
- ABILITIES SETTING (result edit): SELECT "BEFORE" -> "RESET"; skill requirement box "必要" -> "Need"
  ("Need 25 AP"); requirement panel buttons Shoot / Melee / Def. / Mobil., header "Skill Req.".
- Faction name plates (18): the rule and katakana reading under the official English name removed.
- Not checked in game yet (pause screen in battle, ABILITIES SETTING).

### Voice (subtitle groundwork)
- `tools/adi.py`: STREAM.MB voice clips decoded (SShd/SSbd PS-ADPCM, data at 0x30, sectors relative
  to the archive data start). `tools/transcribe.py`: Whisper large-v3 (faster-whisper, GPU) in a
  separate 64-bit Python 3.11 env (`work/bin/whisper/`, git-ignored; the project Python is 32-bit).
- 2,339 story clips transcribed (Progress `evp`, Chronicle `evc`, tutorial `evt`, briefing `br_`) to
  `work/source/voice/transcripts.jsonl` (Japanese, git-ignored). No subtitles in the game yet.

### Builds
- 0.1.4 kept as `work/output/patches/Gundam_Climax_UC_EN_v0.1.4.xdelta` (decode verified).

## 0.1.4 — 2026-11-10 (local build, not released)

Output: `work/output/Gundam_Climax_UC_EN_v0.1.4.iso` (SHA-1 73daaba29f67dca8f90dd35c7b84be11f9270ae6).

### Text
- Memory card messages (`mcd_msg_data.csv`, 34 messages + slot labels, new group `system`): standard
  PS2 English ("memory card (PS2)", "MEMORY CARD slot 1"); reviewed (accuracy, editorial, proofread in
  one pass for this small boilerplate set). Quoted multi-line CSV cells are now supported by
  extraction and insertion (`textlib.extract_qcsv`, `insert_text.build_qcsv`, byte-identical
  round trip). Checked in game (memory card check at boot).
- Row ids are now permanent across re-extraction (new text gets the next free id; status, notes and
  history are kept for every row, translated or not).

### Save title
- The PS2 browser title of the save (icon.sys in saga_mc.fpk) is "MOBILE SUIT GUNDAM / CLIMAX U.C."
  in full-width letters (`tools/save_title.py`). Only saves created with the patched game show it.

### Textures
- Japanese layered over English lettering is now handled by redrawing the image with the game's own
  English wording and the game font (Japanese removed):
  - rank plates (Master Sergeant ... Colonel, 7 plates, 7 copies each, plus result-edit copies);
  - personality plates GENTLE / HOT-BLOOD / COOL (status icons, character edit, result edit);
  - stat labels ARMOR / CP / INFIGHTING / MAIN WEAPON / MOBILITY / NT in the menu, ability, pilot
    parameter and pause designs; CP and NT get a small grey gloss (Condition Pts / Newtype).
- 118 texture files patched (`work/build/tex_report.txt`). The Abilities Introduction screen was not
  reached in the emulator; the plates and labels were checked as rendered images.

### Builds
- 0.1.3 kept as `work/output/patches/Gundam_Climax_UC_EN_v0.1.3.xdelta` (decode verified).

## 0.1.3 — 2026-11-10 (local build, not released)

Output: `work/output/Gundam_Climax_UC_EN_v0.1.3.iso` (SHA-1 3cb9dfe606edbad892dc167e9ddc45cf43886397).

### Textures (first texture translations; see `docs/textures.md`)
- Title menu: the seven mode descriptions ("< Tutorial > / Learn the controls hands-on." etc.).
- Briefing: Mission / Victory / Defeat labels.
- Skill plates: 18 active, 43 passive (names = the executable's skill table, so plates and menus
  agree) and 36 MS-skill plates (names follow the glossary: VSBR, I-field, Bug, hide bomb, heat rod,
  psycommu). Background rebuilt per plate family; tag (PASSIVE / ACTIVE / MS SKILL) untouched.
- Result-edit stat labels (Japanese only) → Defense / Condition Pts / Melee / Shooting / Mobility / Newtype.
- 100 texture files, 540 copies across GAME.MB (`work/build/tex_report.txt`).
- New tools: `xts_tool.encode_image` (PNG → XTS, 4/8/32 bpp, round-trip verified lossless),
  `tools/tex_jobs.py`, `tools/tex_make.py`; textures are patched by `tools/build.py`.
- Checked in game: title menu description, briefing labels, MS-skill plate on skill select.
- Not done: stat labels with a Japanese gloss over the English word (menus, pause) — need hand pixel
  repair; other Japanese textures not yet inventoried.

### Font
- "l": the game's glyph is a bare 1 px stem without the grey anti-aliasing column every other narrow
  letter has, so it read as a hairline with a 2 px advance ("Tutorial", "Controls"). Redrawn like
  "i" (`vwf.fix_l_glyph`, advance 3 px). Comparison: `work/ui/font_compare/l_fix_4x.png`.

### Builds
- 0.1.2 kept as `work/output/patches/Gundam_Climax_UC_EN_v0.1.2.xdelta` (decode verified).

## 0.1.2 — 2026-11-10 (local build, not released)

Output: `work/output/Gundam_Climax_UC_EN_v0.1.2.iso` (SHA-1 3aef154875737ad284e4f4cbd4aa62c64ff89c09).
Text is the same as 0.1.0 / 0.1.1.

### Font
- Bold letters reverted by request (`vwf.BOLD = False`): back to the game's original thin 1x Latin
  glyphs of 0.1.0.
- The "j" fix is kept as its own step (`vwf.fix_j_hook`): the hook now reaches 2 px left of the stem
  instead of 4, so "Objectives", "adjust", "major" no longer show a gap. Every other glyph and width
  is identical to 0.1.0 (checked by diffing the built font). Comparison: `work/ui/font_compare/thin_jfix_4x.png`.
- Checked in game (tutorial select); all 423 cards still fit.

### Builds
- 0.1.1 kept as `work/output/patches/Gundam_Climax_UC_EN_v0.1.1.xdelta` (decode verified).

## 0.1.1 — 2026-11-10 (local build, not released)

Output: `work/output/Gundam_Climax_UC_EN_v0.1.1.iso` (SHA-1 f9fd8adc6b41d1d9228e8023d99f77e01687c60e).
Text is the same as 0.1.0; only the font changed.

### Font
- Bold Latin letters: the game's own half-width glyphs are emboldened by 1 px (2 px vertical stems,
  1 px horizontals), the construction of the Skies of Arcadia font used by the Seireiki Rayblade patch,
  while keeping the game's letter shapes (`vwf.BOLD`, `vwf.embolden_halfwidth`).
- "j": hook shortened to 1 px left of the stem; the old glyph left a gap after the previous letter
  ("Ob jectives").
- Widths grow about 1 px per letter. Re-checked: font file 724,160 / 724,992 bytes allocated; all 423
  cards still wrap within their lines; widest mission-intro line 458 px; briefing titles still end at
  the Japanese right edge (checked in game). Comparisons: `work/ui/font_compare/`.

### Builds
- 0.1.0 kept as `work/output/patches/Gundam_Climax_UC_EN_v0.1.0.xdelta` (99 KB, decode verified).

## 0.1.0 — 2026-11-10 (local build, not released)

First full English build: every text string in GAME.MB, the player-facing text in the executable,
and the card gallery (encyclopedia) are translated and reviewed. Graphics with Japanese text
(textures: main-menu mode descriptions, some headings) are not translated yet.

Output: `work/output/Gundam_Climax_UC_EN_v0.1.0.iso` (SHA-1 3134c90f26c77c4a3bd5c11e98c10c115e068f9f).

### Translation
- 2,880 of 2,886 strings translated (the other 6 are binary data misread as text and stay untouched);
  423 / 423 cards. Coverage check on the built ISO: 45 Japanese hits left, all of them those binary
  values (`work/build/coverage_v010.txt`).
- Groups: mission intros (842), UI (621), unit/skill data (404), executable text (297), briefings
  (283), stage data (283), pilot history (156), cards (423).
- Workflow per BASE_RULES: translation in slices of ≤ 80–210 rows with a per-slice glossary excerpt,
  then accuracy review, editorial pass, accuracy recheck of substantive editorial changes,
  proofreading, and a final name script (`tools/names_fix.py`). Every applied edit is logged in the
  row's `history`.
- House style decisions: narration in past tense (present only where the Japanese marks "now");
  objectives "Destroy the X" / "Engage <faction> MS forces"; ranks Ensign / Lieutenant / Captain /
  Major / Lt. Col. / Colonel (少尉 = Ensign, as on the official site); 新連邦 = "New Federation (F91)";
  battle names in the pilot history are noun phrases for the "Fought in %s," template; the game's own
  English subtitles (e.g. "On the Earth orbit", "Side3 Area") are kept as written.

### Layout
- Leading full-width padding is re-created for English (`textenc.recentre`): briefing stage titles are
  right-aligned (17 cells × 18 px), other padded lines keep their centre. Verified in game on the
  briefing header and against the original Japanese screen.
- Full-width advance measured in game: 18 px (`textenc.FULL_PX`), not the 20 px glyph cell.
- Pilot-history continuation lines aligned to the text column (13 spaces / 3 full-width + 2 spaces).
- Japanese 「…」 stage titles: one leading space before the English quote so it clears the box border.
- Shared intro row S01919 gets a per-occurrence override ("The Crossbone Vanguard") where it starts a
  sentence (`en_override`, supported by insert and kept by re-extraction).

### Executable text (`tools/elf_text.py`, `docs/elf_text.md`)
- 322 strings: 275 in place, 47 relocated into developer-only debug strings and the freed slots of
  relocated strings (2,040 bytes of pool left). File size and segments unchanged.

### Fixes
- FPKs with two members of the same name (vs_setting2.fpk): every copy is now patched.

### Glossary
- 126 characters, 108 mobile suits, 224 terms (`work/glossary/`).
- Name source order: official English site (en.gundam-official.com, `_official_names.json`) → Gundam
  Wiki → game romanization. Official spellings adopted: Aina / Ginius Sakhalin, Jacqueline Simon,
  Ple-Two, Aboly, Kampfer, Nu Gundam, Alpha Azieru, Hyaku-Shiki, Gaza C, Quin Mantha, Qubeley Mk-2,
  Berga-Dalas, Vigna-Ghina, Gundam GP02A Physalis, Gundam GP03 Dendrobium, Hizack (E.F.S.F.).

### Tools
- `tools/mb_tool.py`: MB13CDVD archive list/extract/build.
- `tools/fpk_tool.py`: FPK container parse/extract (recursive)/build.
- `tools/sjis_scan.py`, `tools/elf_strings.py`: Shift-JIS scanners.
- `tools/mipsdis.py`, `tools/asm.py`: EE disassembly (capstone) and assembly (keystone + own branch encoding).
- `tools/ufm_tool.py`: font decoder/renderer (JIS-indexed map, 20×18 2bpp glyphs).
- `tools/vwf.py`: VWF font builder + `HalfWidth` patch.
- `tools/textlib.py`, `tools/extract_text.py`: C2B / fixed-record / CSV text extraction → `strings.json`.
- `tools/cards.py`, `tools/textenc.py`: card gallery text, pixel measuring, wrapping, alignment.
- `tools/insert_text.py`, `tools/build.py`: insertion and ISO build (in place, sector-allocation checked).
- `tools/elf_text.py`: executable text, in place or relocated with references repointed.
- `tools/slices.py`, `tools/slice_gloss.py`: translator slices with per-slice glossary excerpts.
- `tools/review_export.py`, `tools/review_apply.py`: scene-order review exports (shared rows tagged),
  dry-run-first application of review edits; applied outputs move to `review/out/applied/`.
- `tools/names_fix.py`: corpus-wide name/term rules, run after agent edits.
- `tools/official_check.py`: glossary vs official English site.
- `tools/coverage.py`, `tools/strip_jp.py`, `tools/xts_tool.py`.
- Debug kit `tools/debug/`: portable PCSX2 control, PINE client, pad-hook input injection, frame clock,
  safe halt, savestate screenshots, function tracer. See `docs/debug_tools.md`.

### Known issues / not done
- Textures with Japanese text are untranslated (main-menu mode descriptions, unit-viewer button help,
  some headings).
- Skill descriptions: Japanese aligns "CP: n" in a column with full-width spaces; the English uses two
  spaces (the 63-byte slots cannot hold the padding), so the cost column is ragged.
- Not yet checked in game: card gallery with this build's text (card_info is loaded at boot), pilot
  history / retirement screens, skill lists, VS setup screens.

## 0.0.1-vwftest (test only, not a release)
- VWF font + ELF patch. Verified ASCII renders proportionally.
- Kept as `work/output/patches/Gundam_Climax_UC_EN_v0.0.1-vwftest.xdelta` (17 KB, against the original
  ISO; decode verified, SHA-1 5c6f206127115f21692f61c2d8abb6ca92130eb7). ISO removed.

## Tooling note
- `tools/patches.py` (make / verify / retire / prune) keeps older builds as xdelta patches, at most 10.
  xdelta3 3.1.0 (official release, github.com/jmacd/xdelta-gpl) lives in `work/bin/xdelta3/` (git-ignored).
