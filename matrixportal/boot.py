# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""Boot configuration - Controls filesystem write permissions.

By default, the filesystem is writable by the computer (USB host).
To enable logging to flash, ground pin A1 before powering on the device.

Modes:
- A1 floating (default): Filesystem writable by computer, read-only to CircuitPython
- A1 grounded: Filesystem writable by CircuitPython (enables crash logging)
Note: Changes only take effect after hard reset (power cycle or reset button).
"""

import storage
import board
import digitalio

# Check if A1 is grounded to enable logging mode
write_mode_pin = digitalio.DigitalInOut(board.A1)
write_mode_pin.direction = digitalio.Direction.INPUT
write_mode_pin.pull = digitalio.Pull.UP

# If pin is LOW (grounded), enable CircuitPython write access
if not write_mode_pin.value:
    storage.remount("/", readonly=False)
    print("[boot.py] Logging mode: Filesystem writable by CircuitPython")
else:
    print("[boot.py] Normal mode: Filesystem writable by computer")
