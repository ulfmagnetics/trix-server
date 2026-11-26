# SPDX-FileCopyrightText: 2026
# SPDX-License-Identifier: MIT

"""Runs when CircuitPython enters safe mode (CircuitPython 8.1+).

Without this file, a hard fault leaves the board sitting in safe mode until
someone presses reset. Here we record why, in NVM, and reset immediately so
code.py gets another go. The next boot reports the reason via the crash log
and GET /crash/counter.

Kept dependency-free and must stay a .py file (not compiled to .mpy).
NVM offsets must match health.py.
"""

import microcontroller
import supervisor

NVM_LAST_CAUSE = 1
NVM_COUNT_BASE = 2
NVM_SAFE_REASON = 16
NVM_SAFE_REASON_LEN = 32
CAUSE_SAFEMODE = 4

reason = str(supervisor.runtime.safe_mode_reason).split(".")[-1]

# Safe modes a person asked for (holding the button at boot, or
# supervisor.reload into safe mode from the REPL) are left alone.
if reason not in ("USER", "PROGRAMMATIC"):
    try:
        encoded = reason.encode("ascii")[:NVM_SAFE_REASON_LEN]
        microcontroller.nvm[NVM_SAFE_REASON:NVM_SAFE_REASON + NVM_SAFE_REASON_LEN] = (
            encoded + b"\x00" * (NVM_SAFE_REASON_LEN - len(encoded))
        )
        microcontroller.nvm[NVM_LAST_CAUSE] = CAUSE_SAFEMODE
        idx = NVM_COUNT_BASE + CAUSE_SAFEMODE - 1
        microcontroller.nvm[idx] = (microcontroller.nvm[idx] + 1) & 0xFF
    except Exception:
        pass
    microcontroller.reset()
