"""Start/stop the project's portable PCSX2 (only that exact executable path).

Usage:
  python emu.py start [iso] [--state FILE]
  python emu.py stop
  python emu.py status
"""
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
EXE = os.path.join(ROOT, 'work', 'emulator', 'pcsx2', 'pcsx2-qt.exe')
DEFAULT_ISO = os.path.join(ROOT, 'Mobile Suit Gundam - Climax U.C. (Japan).iso')

sys.path.insert(0, os.path.dirname(__file__))
from pine import Pine  # noqa: E402


def our_pids():
    """PIDs of pcsx2-qt.exe whose image path is exactly EXE."""
    ps = ('Get-CimInstance Win32_Process -Filter "Name=\'pcsx2-qt.exe\'" | '
          'ForEach-Object { \"$($_.ProcessId)|$($_.ExecutablePath)\" }')
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True).stdout
    pids = []
    for line in out.splitlines():
        if '|' in line:
            pid, path = line.split('|', 1)
            if os.path.normcase(os.path.abspath(path.strip())) == os.path.normcase(EXE):
                pids.append(int(pid))
    return pids


def stop():
    for pid in our_pids():
        subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True)
    for _ in range(50):
        if not our_pids():
            return True
        time.sleep(0.2)
    return False


def wait_pine(timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            p = Pine(timeout=2)
            p.version()
            return p
        except Exception:
            time.sleep(0.5)
    raise RuntimeError('PINE did not come up')


def start(iso=None, state=None):
    stop()
    args = [EXE, '-batch', '-nofullscreen']
    if state:
        args += ['-statefile', state]
    else:
        args += ['-fastboot']
    args += ['--', os.path.abspath(iso) if iso else DEFAULT_ISO]
    subprocess.Popen(args, cwd=os.path.dirname(EXE))
    p = wait_pine()
    return p


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'start':
        st = None
        if '--state' in a:
            k = a.index('--state'); st = a[k + 1]; del a[k:k + 2]
        p = start(a[1] if len(a) > 1 else None, st)
        print('started:', p.version())
    elif a[0] == 'stop':
        print('stopped' if stop() else 'still running')
    elif a[0] == 'status':
        print(our_pids())
