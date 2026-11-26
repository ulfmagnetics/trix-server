# SPDX-FileCopyrightText: 2026
# SPDX-License-Identifier: MIT

"""Finish reading a request body that adafruit_httpserver handed over short.

adafruit_httpserver (4.7.1) reads the body until Content-Length bytes have
arrived, but when a recv times out it silently returns what it has so far.
trix-hub then sees "Invalid bitmap size: 1440/2880/4320 bytes" or "Invalid
bitmap data (size: 0)". The rest of the upload is often still in flight, so
keep reading from the same socket for a little longer before giving up.

No CircuitPython-only imports, so this can be unit-tested on a PC.
"""

import errno
import time

_RETRY_ERRNOS = (errno.ETIMEDOUT, errno.EAGAIN)


def complete_body(sock, body, expected, deadline_s=5.0, chunk=2048):
    """Return body topped up to `expected` bytes from `sock`, if possible.

    Args:
        sock: the request's connection socket (request.connection)
        body: bytes already received
        expected: Content-Length
        deadline_s: total extra time allowed for the remainder
        chunk: recv buffer size

    Returns:
        bytes: the body, which may still be short if the client stopped
        sending (peer closed or deadline passed). The caller validates length.
    """
    if expected <= 0 or len(body) >= expected:
        return body

    parts = [bytes(body)]
    got = len(body)
    buf = bytearray(chunk)
    end = time.monotonic() + deadline_s

    while got < expected and time.monotonic() < end:
        try:
            n = sock.recv_into(buf, min(chunk, expected - got))
        except OSError as ex:
            if ex.errno in _RETRY_ERRNOS:
                continue  # nothing yet; try again until the deadline
            raise
        if not n:
            break  # peer closed the connection
        parts.append(bytes(buf[:n]))
        got += n

    return b"".join(parts)
