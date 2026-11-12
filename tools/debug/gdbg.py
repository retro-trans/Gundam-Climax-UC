"""Game debug helper: input injection, frame clock, safe halt, screenshots.

Installs a hook at the end of scePadRead (debug cave, see addrs.py):
    cave: ld   $ra,0x40($sp)          ; replaced instruction
          beqz $s2, out
          lui  $t0, hi(MAILBOX)
          lhu  $t1, lo(MB_BUTTONS)($t0)
          lhu  $t2, 2($s2)
          nor  $t1, $t1, $zero
          and  $t2, $t2, $t1
          sh   $t2, 2($s2)               ; raw data is active-low: clear bit = pressed
          lw   $t3, lo(MB_FRAME)($t0)
          addiu $t3, $t3, 1
          sw   $t3, lo(MB_FRAME)($t0)
    spin: lw   $t4, lo(MB_HALT_REQ)($t0)
          beqz $t4, out
          addiu $t5, $zero, 1
          sw   $t5, lo(MB_HALTED)($t0)
          b    spin
          nop
    out:  sw   $zero, lo(MB_HALTED)($t0)   (only if $t0 set; harmless otherwise skipped)
          j    RESUME
          nop

Usage:
  python gdbg.py install
  python gdbg.py press <button>[+button...] [frames_hold] [frames_release]
  python gdbg.py seq "circle,circle,down,circle" [wait_frames]
  python gdbg.py shot <out.png>
  python gdbg.py halt | resume | reset
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from addrs import *  # noqa
from pine import Pine  # noqa
import savestate  # noqa

from keystone import Ks, KS_ARCH_MIPS, KS_MODE_MIPS32, KS_MODE_LITTLE_ENDIAN


def hi(a):
    return ((a + 0x8000) >> 16) & 0xFFFF


def lo(a):
    v = a & 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def build_cave():
    ks = Ks(KS_ARCH_MIPS, KS_MODE_MIPS32 + KS_MODE_LITTLE_ENDIAN)
    src = """
        beqz $s2, out
        nop
        lui $t0, {h}
        lhu $t1, {b}($t0)
        lhu $t2, 2($s2)
        nor $t1, $t1, $zero
        and $t2, $t2, $t1
        sh $t2, 2($s2)
        lw $t3, {f}($t0)
        addiu $t3, $t3, 1
        sw $t3, {f}($t0)
    spin:
        lw $t4, {r}($t0)
        beqz $t4, done
        addiu $t5, $zero, 1
        sw $t5, {hd}($t0)
        b spin
        nop
    done:
        sw $zero, {hd}($t0)
    out:
        j {resume}
        nop
    """.format(h=hi(MAILBOX), b=lo(MB_BUTTONS), f=lo(MB_FRAME), r=lo(MB_HALT_REQ), hd=lo(MB_HALTED),
               resume=SCE_PAD_READ_RESUME)
    enc, _ = ks.asm(src, DEBUG_CAVE + 4)
    # keystone may fill delay slots itself; we used explicit nops, keep 'noreorder' semantics by check
    return struct.pack('<I', SCE_PAD_READ_EPILOGUE_WORD) + bytes(enc)


def j_insn(target):
    return 0x08000000 | ((target >> 2) & 0x3FFFFFF)


class Dbg:
    def __init__(self, pine=None):
        self.p = pine or Pine()

    def installed(self):
        return self.p.r32(MB_MAGIC) == 0x47424447 and \
            self.p.r32(SCE_PAD_READ_EPILOGUE) == j_insn(DEBUG_CAVE)

    def install(self):
        if self.installed():
            return 'already'
        code = build_cave()
        region = self.p.read(DEBUG_CAVE, 0x1000)
        if any(region[:len(code)]) and region[:len(code)] != code:
            raise RuntimeError('debug cave not free')
        if any(region[0xF00:0xF20]):
            raise RuntimeError('mailbox not free')
        self.p.write(DEBUG_CAVE, code)
        self.p.write(MAILBOX, b'\0' * 0x14)
        self.p.w32(MB_MAGIC, 0x47424447)
        # word write is atomic for the EE: the hooked insn becomes 'j cave'; delay slot is the
        # original next insn (ld $s3,...) which is fine to run before the cave? No - keep it
        # in order: the cave re-executes nothing after; RESUME = epilogue+4 re-runs ld $s3.
        # The delay slot runs 'ld $s3,0x30($sp)' first and RESUME runs it again: harmless.
        self.p.w32(SCE_PAD_READ_EPILOGUE, j_insn(DEBUG_CAVE))
        return 'installed'

    def frame(self):
        return self.p.r32(MB_FRAME)

    def wait_frames(self, n):
        # scePadRead runs once per frame per open port; count calls
        f0 = self.frame()
        t0 = time.time()
        while self.frame() - f0 < n:
            if time.time() - t0 > 30:
                raise RuntimeError('frame clock stalled')
            time.sleep(0.005)

    def press(self, buttons, hold=4, release=4):
        mask = 0
        for b in buttons:
            mask |= BTN[b]
        self.p.write(MB_BUTTONS, struct.pack('<H', mask))
        self.wait_frames(hold)
        self.p.write(MB_BUTTONS, b'\0\0')
        self.wait_frames(release)

    def halt(self, timeout=10):
        self.p.w32(MB_HALT_REQ, 1)
        t0 = time.time()
        while self.p.r32(MB_HALTED) != 1:
            if time.time() - t0 > timeout:
                raise RuntimeError('halt timeout')
            time.sleep(0.005)

    def resume(self):
        self.p.w32(MB_HALT_REQ, 0)

    def reset(self):
        self.p.write(MB_BUTTONS, b'\0\0')
        self.p.w32(MB_HALT_REQ, 0)

    def shot(self, out, slot=9):
        return savestate.shot(out, slot, self.p)

    def flush_rec(self, slot=8):
        """PCSX2's EE recompiler does not see code written over PINE in blocks it already compiled.
        Saving and reloading a savestate drops every compiled block, so patched code takes effect."""
        old_m = time.time() - 0.5
        self.p.save_state(slot)
        for _ in range(150):
            sp = savestate.slot_path(slot)
            if sp and os.path.getmtime(sp) > old_m:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError('flush: savestate not written')
        time.sleep(0.5)
        self.p.load_state(slot)
        time.sleep(1.0)

    # ------------------------------------------------------------ tracer
    TRACE_CAVE = DEBUG_CAVE + 0x400      # code
    TRACE_BUF = DEBUG_CAVE + 0x800       # u32 count, then 7-word entries (a0 a1 a2 a3 ra sp gp)
    TRACE_MAX = 64

    def trace(self, addr, seconds=5.0, action=None, flush=True):
        """Log the first TRACE_MAX calls of the function at addr (its first two instructions
        must not be branches and must not be branch targets except addr itself)."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from asm import asm
        orig = self.p.read(addr, 8)
        w0, w1 = struct.unpack('<2I', orig)
        for w in (w0, w1):
            op = w >> 26
            if op in (1, 2, 3, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17) or (op == 0 and (w & 0x3F) in (8, 9)):
                raise RuntimeError('branch in hooked instructions')
        buf = self.TRACE_BUF
        code = asm([
            'lui $t8, %d' % hi(buf),
            'lw $t9, %d($t8)' % lo(buf),
            'sltiu $at, $t9, %d' % self.TRACE_MAX,
            'beqz $at, done',
            'nop',
            'sll $at, $t9, 3',          # *8
            'subu $at, $at, $t9',       # *7
            'sll $at, $at, 2',          # *28 -> 7 words per entry (count word + pad)
            'addu $at, $at, $t8',
            'sw $a0, %d($at)' % lo(buf + 4),
            'sw $a1, %d($at)' % lo(buf + 8),
            'sw $a2, %d($at)' % lo(buf + 12),
            'sw $a3, %d($at)' % lo(buf + 16),
            'sw $ra, %d($at)' % lo(buf + 20),
            'sw $sp, %d($at)' % lo(buf + 24),
            'sw $gp, %d($at)' % lo(buf + 28),
            'addiu $t9, $t9, 1',
            'sw $t9, %d($t8)' % lo(buf),
            'done:',
            '.word 0x%08X' % w0,
            '.word 0x%08X' % w1,
            'j 0x%X' % (addr + 8),
            'nop',
        ], self.TRACE_CAVE)
        self.halt()
        try:
            self.p.write(self.TRACE_CAVE, code)
            self.p.write(buf, b'\0' * (4 + 28 * self.TRACE_MAX))
            self.p.write(addr, struct.pack('<2I', j_insn(self.TRACE_CAVE), 0))
            if flush:
                self.flush_rec()
        finally:
            self.resume()
        try:
            if action:
                action(self)
            else:
                time.sleep(seconds)
        finally:
            self.halt()
            self.p.write(addr, orig)
            if flush:
                self.flush_rec()
            self.resume()
        n = self.p.r32(buf)
        out = []
        raw = self.p.read(buf + 4, 28 * min(n, self.TRACE_MAX) + 4)
        for i in range(min(n, self.TRACE_MAX)):
            out.append(struct.unpack_from('<7I', raw, i * 28))
        return out


    STR_MAX = 48                          # string mode: entries of ra + 32 bytes copied from a reg

    def trace_str(self, addr, reg='a0', seconds=5.0, action=None, n=32, maxn=None, flush=True):
        """Like trace(), but each entry is (ra, n bytes read from the pointer in reg)."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from asm import asm
        orig = self.p.read(addr, 8)
        w0, w1 = struct.unpack('<2I', orig)
        for w in (w0, w1):
            op = w >> 26
            if op in (1, 2, 3, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17) or (op == 0 and (w & 0x3F) in (8, 9)):
                raise RuntimeError('branch in hooked instructions')
        buf, es = self.TRACE_BUF, 4 + n
        mx = maxn or self.STR_MAX
        assert 4 + es * mx <= 0x700, 'trace buffer overflow'
        code = [
            'lui $t8, %d' % hi(buf),
            'lw $t9, %d($t8)' % lo(buf),
            'sltiu $at, $t9, %d' % mx,
            'beqz $at, done',
            'nop',
            'addiu $at, $zero, %d' % es,
            'mult $t9, $at',
            'mflo $at',
            'addu $at, $at, $t8',
            'sw $ra, %d($at)' % lo(buf + 4),
            'move $t7, $%s' % reg,
        ]
        # copy loop (cave is only 0x400 bytes, so no unrolling): t7 = src, at = dst, t5 = end
        code += [
            'addiu $t5, $t7, %d' % n,
            'copy:',
            'lwl $t6, 3($t7)',
            'lwr $t6, 0($t7)',
            'sw $t6, %d($at)' % lo(buf + 8),
            'addiu $t7, $t7, 4',
            'bne $t7, $t5, copy',
            'addiu $at, $at, 4',
        ]
        code += [
            'addiu $t9, $t9, 1',
            'sw $t9, %d($t8)' % lo(buf),
            'done:',
            '.word 0x%08X' % w0,
            '.word 0x%08X' % w1,
            'j 0x%X' % (addr + 8),
            'nop',
        ]
        code = asm(code, self.TRACE_CAVE)
        self.halt()
        try:
            self.p.write(self.TRACE_CAVE, code)
            self.p.write(buf, b'\0' * (4 + es * mx))
            self.p.write(addr, struct.pack('<2I', j_insn(self.TRACE_CAVE), 0))
            if flush:
                self.flush_rec()
        finally:
            self.resume()
        try:
            if action:
                action(self)
            else:
                time.sleep(seconds)
        finally:
            self.halt()
            self.p.write(addr, orig)
            if flush:
                self.flush_rec()
            self.resume()
        cnt = min(self.p.r32(buf), mx)
        raw = self.p.read(buf + 4, es * cnt + 4)
        return [(struct.unpack_from('<I', raw, i * es)[0], raw[i * es + 4:i * es + es])
                for i in range(cnt)]


if __name__ == '__main__':
    a = sys.argv[1:]
    d = Dbg()
    if a[0] == 'install':
        print(d.install())
    elif a[0] == 'press':
        d.press(a[1].split('+'), *(int(x) for x in a[2:4]))
    elif a[0] == 'seq':
        wait = int(a[2]) if len(a) > 2 else 20
        for b in a[1].split(','):
            b = b.strip()
            if b.startswith('w'):
                d.wait_frames(int(b[1:]))
            else:
                d.press(b.split('+'))
                d.wait_frames(wait)
    elif a[0] == 'shot':
        print(d.shot(a[1]))
    elif a[0] == 'halt':
        d.halt(); print('halted at frame', d.frame())
    elif a[0] == 'resume':
        d.resume()
    elif a[0] == 'reset':
        d.reset()
    elif a[0] == 'tracestr':      # tracestr <addr> [seconds] [reg]
        for ra, t in d.trace_str(int(a[1], 16), a[3] if len(a) > 3 else 'a0', float(a[2]) if len(a) > 2 else 5.0):
            print('%08X %s' % (ra, t.split(b'\0')[0].decode('ascii', 'replace')))
    elif a[0] == 'frame':
        print(d.frame())
