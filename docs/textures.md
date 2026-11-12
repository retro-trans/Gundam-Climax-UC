# Translated textures

Pipeline: `tools/tex_jobs.py` → `work/translation/en/textures.json` (what to translate, Japanese,
English, style) → `tools/tex_make.py` (draw + encode) → `tools/build.py` (patches every copy).

- Format: XTS containers, 4-bit images with their own 16-colour CLUT, stored upside down (the game
  draws them flipped). `xts_tool.encode_image` re-quantizes an edited image to 16/256 colours and
  rewrites only that image's CLUT and pixels; file size and layout never change.
- Copies: the same texture file is often packed into several FPKs (skill plates: 7 archives).
  `tex_make.copies` finds every byte-identical extracted copy and the build replaces the original
  bytes in each GAME.MB entry (`work/build/tex_report.txt` lists the counts).
- Lettering uses the game's own font (built `s18rm04.ufm`, same glyphs as the in-game text). The
  space glyph is never drawn (it carries a baseline pixel row; the game skips it too).
- Preview: `python tools/tex_make.py preview` → `work/translation/en/tex/` (upright PNGs + contact
  sheet, original on the left).

## Done (0.1.3)
| Texture | Archive(s) | Style |
|---|---|---|
| Title-menu mode descriptions `sub_01`–`sub_07` | saga_title0/1 | header + line, grey on black |
| Briefing labels Mission / Victory / Defeat (`mission_text`) | briefingb, briefingb.pack | grey text with alpha |
| Active-skill plates (18) | 7 archives each | plate |
| Passive-skill plates (43) | 7 archives each | plate |
| MS-skill plates (36; `???` kept) | msskill_panel, unitselectb, t_unitselectb | plate |
| Result-edit stat labels (6, Japanese only) | resultedit | grey + white outline, right-aligned |

Plates: the background is rebuilt per family (AS / PS / MS) from all plates — in each plate the name
area's text pixels are found by brightness against the row's background, every pixel takes the median
of the plates where it is not text, and the name rows are flattened (the plate is a vertical
gradient). The PASSIVE / ACTIVE / MS SKILL tag is untouched. Names: bold white with a dark shadow;
regular weight when the bold name is wider than the plate (Emergency Guard, Ground Combat+, the
long Pilot+ names, High-Speed Mode, Mass Afterimage, Hidden Arm Guard, MS Dummy Balloon, Psycommu
Boost, Shoulder Charge, Sticky Launcher).

## Japanese layered over English (0.1.4): redrawn
Stat labels (menu / ability / pilot-parameter / pause designs), rank plates (Class01-07) and
personality plates draw Japanese over English lettering. Removing the Japanese automatically failed
(grey bevel pixels in the English letters; inpainting and tag boxes looked wrong), so these images are
redrawn with the game font and the image's own English wording (styles `stat_word`, `rank_plate`,
`personality`): rank plates keep the bevelled plate (interior flattened, text embossed), the other
two are outlined words on transparent backgrounds. The English is smaller than the original display
lettering but complete.

## Not done
- Other textures with Japanese not yet inventoried (card gallery headers, history screens, etc.).
- Chronicle stage select: the series title logos on the left (ガンダム, ポケットの中の戦争, 小説 / Starlight...
  style plates) are Japanese logo textures (seen 2026-11-11, 0.1.6). Official English series titles
  would go here (Mobile Suit Gundam, War in the Pocket, ...).
- MS select: the same series logos sit above the unit name (e.g. 第08MS小隊).
- MS skill plates follow the MS-select panel names (`unitweapon.fpk` `wp_<unit>.xts`, one 128x128
  image per unit, 7 rows: Charge Lv3/2/1, sub weapon, infighting, defense, SP skill). Mapping and
  the corrected spellings are in `tools/tex_jobs.py` (`MS`).
