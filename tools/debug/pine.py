"""PINE IPC client for the project's portable PCSX2 (TCP on Windows).

Port comes from env GUNDAM_PINE_PORT (default 28111, set in work/emulator/pcsx2/inis/PCSX2.ini).
EE addresses are plain 0x00xxxxxx virtual addresses.
"""
import os
import socket
import struct

PORT = int(os.environ.get('GUNDAM_PINE_PORT', '28111'))

OP_R8, OP_R16, OP_R32, OP_R64 = 0, 1, 2, 3
OP_W8, OP_W16, OP_W32, OP_W64 = 4, 5, 6, 7
OP_VERSION, OP_SAVE, OP_LOAD, OP_TITLE, OP_ID, OP_UUID, OP_GAMEVER, OP_STATUS = 8, 9, 10, 11, 12, 13, 14, 15


class PineError(Exception):
    pass


class Pine:
    def __init__(self, port=PORT, timeout=10.0):
        self.s = socket.create_connection(('127.0.0.1', port), timeout=timeout)

    def close(self):
        self.s.close()

    def _recv(self, n):
        b = b''
        while len(b) < n:
            c = self.s.recv(n - len(b))
            if not c:
                raise PineError('connection closed')
            b += c
        return b

    def _cmd(self, payload):
        self.s.sendall(struct.pack('<I', len(payload) + 4) + payload)
        size = struct.unpack('<I', self._recv(4))[0]
        rest = self._recv(size - 4)
        if rest[0] != 0:
            raise PineError('PINE command failed (op %d)' % payload[0])
        return rest[1:]

    def _batch(self, cmds):
        """cmds: list of payload bytes; returns concatenated reply payload (minus status)."""
        body = b''.join(cmds)
        self.s.sendall(struct.pack('<I', len(body) + 4) + body)
        size = struct.unpack('<I', self._recv(4))[0]
        rest = self._recv(size - 4)
        if rest[0] != 0:
            raise PineError('batch failed')
        return rest[1:]

    # --- memory ---
    def r32(self, a):
        return struct.unpack('<I', self._cmd(struct.pack('<BI', OP_R32, a)))[0]

    def w32(self, a, v):
        self._cmd(struct.pack('<BII', OP_W32, a, v & 0xFFFFFFFF))

    def r8(self, a):
        return self._cmd(struct.pack('<BI', OP_R8, a))[0]

    def w8(self, a, v):
        self._cmd(struct.pack('<BIB', OP_W8, a, v & 0xFF))

    def read(self, a, n, chunk=0x800):
        """Read n bytes (uses batched 64-bit reads)."""
        out = bytearray()
        start = a & ~7
        end = (a + n + 7) & ~7
        p = start
        while p < end:
            cnt = min(chunk, end - p) // 8
            rep = self._batch([struct.pack('<BI', OP_R64, p + 8 * i) for i in range(cnt)])
            out += rep
            p += cnt * 8
        return bytes(out[a - start: a - start + n])

    def write(self, a, data, chunk=0x400):
        data = bytes(data)
        i = 0
        cmds = []
        while i < len(data):
            if (a + i) % 4 == 0 and len(data) - i >= 4:
                cmds.append(struct.pack('<BII', OP_W32, a + i, struct.unpack_from('<I', data, i)[0]))
                i += 4
            else:
                cmds.append(struct.pack('<BIB', OP_W8, a + i, data[i]))
                i += 1
            if len(cmds) >= chunk // 8:
                self._batch(cmds)
                cmds = []
        if cmds:
            self._batch(cmds)

    # --- misc ---
    def version(self):
        r = self._cmd(bytes([OP_VERSION]))
        return r[4:].split(b'\0')[0].decode()

    def status(self):
        return {0: 'running', 1: 'paused', 2: 'shutdown'}.get(struct.unpack('<I', self._cmd(bytes([OP_STATUS])))[0])

    def game_id(self):
        return self._cmd(bytes([OP_ID]))[4:].split(b'\0')[0].decode()

    def save_state(self, slot):
        self._cmd(struct.pack('<BB', OP_SAVE, slot))

    def load_state(self, slot):
        self._cmd(struct.pack('<BB', OP_LOAD, slot))
