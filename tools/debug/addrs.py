"""Named addresses for SLPS-25627 (Mobile Suit Gundam Climax U.C., NTSC-J). EE virtual addresses.

Every value here was found by disassembly (tools/mipsdis.py) or runtime inspection.
See docs/debug_tools.md for how each was found.
"""

# --- libpad -------------------------------------------------------------
SCE_PAD_READ = 0x157558          # int scePadRead(port, slot, u8 *rdata); rdata kept in $s2
SCE_PAD_READ_EPILOGUE = 0x157694  # 'ld $ra,0x40($sp)' (DFBF0040) -> hook site, $s2 = rdata
SCE_PAD_READ_EPILOGUE_WORD = 0xDFBF0040
SCE_PAD_READ_RESUME = 0x157698   # next insn after the hooked one

# --- debug cave (debug tools only, never in a release build) ------------
# Zero at runtime in intro, menus and battle (checked by the installer each time).
DEBUG_CAVE = 0x4AD000            # code
MAILBOX = 0x4ADF00               # +0 u16 buttons to press (active-high)
MB_BUTTONS = MAILBOX + 0x0
MB_FRAME = MAILBOX + 0x4         # u32 incremented per scePadRead call (port 0 and 1 both)
MB_HALT_REQ = MAILBOX + 0x8      # u32 != 0 -> spin at the hook (safe halt)
MB_HALTED = MAILBOX + 0xC        # u32 1 while spinning
MB_MAGIC = MAILBOX + 0x10        # 'GDBG' when installed

# --- font ---------------------------------------------------------------
FONT_FILE_NAME = 0x32DD50        # "s18rm04.ufm"
FONT_LOADER = 0x1F4F50           # loads s18rm04.ufm via FILE_LOAD, handle at gp-0x7C24
FILE_LOAD = 0x16A700

# --- pad bits (libpad rdata[2..3] as little-endian u16, active-low in raw data) ---
BTN = {
    'select': 0x0001, 'l3': 0x0002, 'r3': 0x0004, 'start': 0x0008,
    'up': 0x0010, 'right': 0x0020, 'down': 0x0040, 'left': 0x0080,
    'l2': 0x0100, 'r2': 0x0200, 'l1': 0x0400, 'r1': 0x0800,
    'triangle': 0x1000, 'circle': 0x2000, 'cross': 0x4000, 'square': 0x8000,
}
