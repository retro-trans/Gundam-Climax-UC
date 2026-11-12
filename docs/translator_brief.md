# Translator brief — Mobile Suit Gundam: Climax U.C. (PS2) → English

Read `BASE_RULES.md` first; everything there applies. This file adds the project specifics.

## Inputs
- Your slice: `work/translation/en/slices/<slice>.json`. Neighbouring slices (same group, previous /
  next number) may be read for context. Rows are in file order, which is scene order.
- Glossary excerpt for your slice: `work/translation/en/slices/<slice>.gloss.json` — every glossary
  entry whose Japanese occurs in the slice, with `en` already set to the form to write. Read this;
  open the full glossary below only (with Grep) for a name that is not in the excerpt.
- Full glossary (spellings are binding): `work/glossary/characters.json`, `mobile_suits.json`,
  `terms.json`. Source order for spellings: the official English site (en.gundam-official.com,
  saved in `_official_names.json`), then the Gundam Wiki, then the game's own romanization. When an entry has `en_game`, write that (ASCII form the game font can draw,
  e.g. "Nu Gundam", "Kampfer"); otherwise write `en`. If a name is missing or marked "unverified", keep the closest attested
  official form and list it under `uncertain` so the orchestrator can research it — never invent.
- Do not edit `strings.json`, `cards.json` or the glossary. Write only your output file.

## Output
`work/translation/en/slices/out/<slice>.json` (UTF-8):
```json
{"slice": "<slice>", "rows_in_slice": N, "rows_examined": N,
 "rows": [{"id": "S00123", "en": "...", "note": "optional: non-obvious decision"},
          {"id": "S00124", "en": "", "flag": "why it was left"}],
 "decisions": ["short notes that apply to several rows"],
 "uncertain": ["row id: what you were unsure of and what you chose"]}
```
Card slices: each row is `{"id": "U-01", "name_en", "label_en", "model_en", "desc_en", "note"}`.

## Text rules for this game
- Output plain ASCII only. Use `'` and `"` (no curly quotes), `...` not `…`, `-` not dashes,
  roman numerals as `II` (ザクⅡ → Zaku II). No full-width characters, no Japanese.
- Keep every placeholder exactly: `%s`, `%d`, `[U.C.0079]` style era tags, `\n` line breaks.
  A `%s` stands for a runtime name (pilot / unit); count its width as ~10 characters.
- Leading full-width spaces in the Japanese are layout padding for centring. Drop them; the
  orchestrator re-centres. Keep the *number* of `\n`-separated lines unless a line has to wrap;
  if the English needs more lines than the Japanese, say so in `note`.
- `max_bytes` is the hard byte budget of the slot (1 byte per ASCII character). Write the full
  line first; only if it exceeds `max_bytes` compress (abbreviate, tighten) — never drop the end
  of a sentence. If it still cannot fit, leave `en` empty and set `flag`.
- Rendered width: the game font averages ~8 px per character (i/l/./: ~3 px, m/w ~10 px).
  Japanese lines are 18 px per full-width character on screen (measured in game; the glyph cell is 20 px). For multi-line text aim for each English line to
  be no wider than the longest Japanese line it replaces (about 2.4 × its Japanese character
  count, in English characters). This is a guide; the orchestrator measures the real fit.
- Mission-intro rows (`mission_intro_*`): each row is one narration line displayed over the
  mission's opening image, in order. One row in, one row out — do not merge or split rows; when a
  sentence runs across rows, cut the English at the matching point. Row 0 of each file is a date
  (`Ｕ.Ｃ. ００７９.１１` → `U.C. 0079.11`); row 1 is often already an English subtitle in
  full-width letters — convert it to normal ASCII text (keep the official wording).
- Briefing rows: titles like `大気圏突入[U.C.0079]\n\nアムロ編 STAGE１` keep their structure
  (`Into the Atmosphere [U.C.0079]\n\nAmuro Story - STAGE 1`). Objective lines are terse imperatives.
- UI rows: menu labels and help lines. Short, conventional console-game English
  ("Back", "Confirm", "Select a stage."). Button names: ○ = Circle, × = Cross, △ = Triangle,
  □ = Square, keep "L1/R1/L2/R2/R3/START/SELECT".
- Data rows (unit, pilot, skill names and descriptions): use glossary names; skill names are
  short (Title Case), descriptions are one sentence.
- Card slices: `name_en` (official name), `label_en` keeps the card number prefix
  (`U01 Gundam`), `model_en` keeps model numbers as written (`RX-78-2`); for pilot/character
  cards `model_jp` is usually an affiliation or reading — translate it. `desc_en` is ONE paragraph;
  the tool wraps it into `desc_lines_max` lines of `line_px` pixels (≈ 47 average characters per
  line, max `line_bytes` bytes per line). Two-line cards therefore hold about 85–90 characters:
  write the full meaning first, then tighten; abbreviations are fine (Fed., MS, Lt., Cmdr.).
  If it cannot fit, keep the full text and set `flag` — do not drop facts.
- ELF rows (`elf_*`, text inside the game executable): skill / faction / rank names, promotion
  messages, default original-pilot names, pilot history and retirement endings. `slot_bytes` is
  the room in place; longer text is moved to a small shared overflow area (about 2.4 KB for the
  whole executable), so aim to stay within `slot_bytes` and go over only when meaning needs it.
  Skill names in 7-byte slots: prefer one short word. The Japanese multi-line entries contain
  `\n` followed by ~11 spaces of indentation — keep the `\n`, drop the spaces. Default pilot names
  (e.g. ダイ・タチバナ) are name romanizations: "Dai Tachibana"; epithet names (猛火のブレイ)
  are translated ("Blaze the Inferno"-style, short).
- Leave untouched anything that is clearly not shown to players (internal labels, file names);
  if unsure, translate and mention it in `note`.

## Report back (final message)
rows examined vs rows in slice, the ids you flagged, and the `uncertain` list in one line each.
