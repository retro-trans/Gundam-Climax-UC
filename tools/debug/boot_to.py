"""Boot an ISO in the project emulator and drive it to a known screen.

Usage: python boot_to.py <iso> <target> [shot.png]
targets:
  title          intro skipped, title screen
  tutorial       first-boot tutorial stage select (no save data)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import emu  # noqa: E402
from gdbg import Dbg  # noqa: E402
from pine import Pine  # noqa: E402


def wait_game(p, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if p.game_id() == 'SLPS-25627':
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError('game did not start')


def wait_hook_safe(p, timeout=60):
    """scePadRead code must be resident and libpad open before installing."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if p.r32(0x157694) == 0xDFBF0040:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError('ELF not loaded')


def boot(iso):
    emu.start(iso)
    p = Pine()
    wait_game(p)
    wait_hook_safe(p)
    time.sleep(3)
    d = Dbg(p)
    d.install()
    return d


def to_title(d):
    d.wait_frames(60)
    d.press(['start'])
    d.wait_frames(240)


def to_tutorial(d):
    to_title(d)
    d.press(['start'])
    d.wait_frames(600)


if __name__ == '__main__':
    iso, target = sys.argv[1], sys.argv[2]
    d = boot(iso)
    {'title': to_title, 'tutorial': to_tutorial}[target](d)
    if len(sys.argv) > 3:
        d.shot(sys.argv[3])
