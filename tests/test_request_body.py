"""Unit tests for matrixportal/request_body.py (run on a PC: python tests/test_request_body.py)."""

import errno
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "matrixportal"))
from request_body import complete_body  # noqa: E402


class FakeSocket:
    """Plays back a script of recv results: bytes, an errno to raise, or b'' for EOF."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def recv_into(self, buf, nbytes):
        self.calls += 1
        if not self.script:
            raise OSError(errno.ETIMEDOUT, "timed out")
        item = self.script.pop(0)
        if isinstance(item, int):
            raise OSError(item, "simulated")
        n = min(len(item), nbytes)
        buf[:n] = item[:n]
        if n < len(item):
            self.script.insert(0, item[n:])
        return n


EXPECTED = 6198
FULL = b"BM" + bytes(range(256)) * 24 + b"\x00" * (EXPECTED - 2 - 256 * 24)


class CompleteBodyTests(unittest.TestCase):
    def test_already_complete_does_not_read(self):
        sock = FakeSocket([])
        self.assertEqual(complete_body(sock, FULL, EXPECTED), FULL)
        self.assertEqual(sock.calls, 0)

    def test_tops_up_after_timeouts(self):
        # Library gave us one TCP segment; the rest arrives after two timeouts.
        sock = FakeSocket([errno.ETIMEDOUT, errno.EAGAIN, FULL[1440:4000], FULL[4000:]])
        self.assertEqual(complete_body(sock, FULL[:1440], EXPECTED), FULL)

    def test_empty_body_completed(self):
        sock = FakeSocket([FULL])
        self.assertEqual(complete_body(sock, b"", EXPECTED), FULL)

    def test_never_reads_past_content_length(self):
        sock = FakeSocket([FULL[2880:] + b"NEXT-REQUEST"])
        out = complete_body(sock, FULL[:2880], EXPECTED)
        self.assertEqual(out, FULL)

    def test_peer_closed_returns_short(self):
        sock = FakeSocket([FULL[1440:3000], b""])
        out = complete_body(sock, FULL[:1440], EXPECTED)
        self.assertEqual(out, FULL[:3000])

    def test_deadline_returns_short(self):
        sock = FakeSocket([errno.ETIMEDOUT] * 100000)
        t0 = time.monotonic()
        out = complete_body(sock, FULL[:4320], EXPECTED, deadline_s=0.2)
        self.assertEqual(out, FULL[:4320])
        self.assertLess(time.monotonic() - t0, 1.0)

    def test_other_oserror_propagates(self):
        sock = FakeSocket([errno.ECONNRESET])
        with self.assertRaises(OSError):
            complete_body(sock, FULL[:1440], EXPECTED)

    def test_no_content_length_is_noop(self):
        sock = FakeSocket([])
        self.assertEqual(complete_body(sock, b"abc", 0), b"abc")


if __name__ == "__main__":
    unittest.main(verbosity=2)
