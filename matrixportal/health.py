# SPDX-FileCopyrightText: 2026
# SPDX-License-Identifier: MIT

"""Self-recovery for trix-server: hardware watchdog, staleness check, gateway ping.

Three independent failure modes, three guards:

1. Frozen main loop (blocked socket call, deadlock in C code)
   -> hardware watchdog resets the chip if the loop stops calling feed().
2. Loop alive but nothing getting through (server socket dead, Wi-Fi wedged)
   -> staleness check: if trix-hub hasn't reached us for too long, reset.
      After a /display the allowed gap is short (TRIX_STALE_MINUTES);
      after a /clear (trix-hub's overnight blank window) and right after boot
      it is long (TRIX_STALE_AFTER_CLEAR_MINUTES).
3. Network link down
   -> ping the default gateway every minute; reset after several consecutive
      failures, but only once a ping has succeeded this boot (so a router that
      ignores ICMP can't cause a boot loop).

Hard faults into safe mode are handled separately by safemode.py.

Every self-initiated reset records its cause in NVM before resetting, so the
next boot (and GET /crash/counter) can report why the board restarted. The
filesystem is normally read-only to CircuitPython (see boot.py), so NVM is the
only persistent store that works in normal mode.
"""

import os
import time
import microcontroller
import supervisor
import wifi

from crash_logger import logger

# ---------------------------------------------------------------------------
# NVM layout. Byte 0 is CrashLogger's boot counter; keep these in sync with
# safemode.py, which can't import this module's dependencies safely.
# ---------------------------------------------------------------------------
NVM_LAST_CAUSE = 1      # cause code of the most recent self-initiated reset
NVM_COUNT_BASE = 2      # bytes 2..7: per-cause counters (wrap at 255)
NVM_SAFE_REASON = 16    # bytes 16..47: last safe-mode reason, ASCII, NUL-padded
NVM_SAFE_REASON_LEN = 32

CAUSE_NONE = 0
CAUSE_WATCHDOG = 1      # detected at boot from cpu.reset_reason
CAUSE_STALE = 2
CAUSE_GATEWAY = 3
CAUSE_SAFEMODE = 4      # written by safemode.py
CAUSE_FATAL = 5         # unhandled error in the main loop / failed recovery
CAUSE_STARTUP = 6       # exception during startup (Wi-Fi, API key, display, server)

CAUSE_NAMES = {
    CAUSE_NONE: "none",
    CAUSE_WATCHDOG: "watchdog",
    CAUSE_STALE: "stale",
    CAUSE_GATEWAY: "gateway",
    CAUSE_SAFEMODE: "safemode",
    CAUSE_FATAL: "fatal",
    CAUSE_STARTUP: "startup",
}


def _setting(name, default):
    """Read an int setting from settings.toml, falling back to default."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bump(cause):
    idx = NVM_COUNT_BASE + cause - 1
    microcontroller.nvm[idx] = (microcontroller.nvm[idx] + 1) & 0xFF


def reset_for(cause, detail=""):
    """Record why we're resetting, then hard-reset the board. Does not return."""
    logger.log_event(f"Self-reset: {CAUSE_NAMES.get(cause, cause)} {detail}", "WARNING")
    try:
        microcontroller.nvm[NVM_LAST_CAUSE] = cause
        _bump(cause)
    except Exception:  # never let bookkeeping block the reset
        pass
    time.sleep(0.5)  # let serial output flush
    microcontroller.reset()


def _safe_mode_reason_from_nvm():
    raw = bytes(microcontroller.nvm[NVM_SAFE_REASON:NVM_SAFE_REASON + NVM_SAFE_REASON_LEN])
    return raw.split(b"\x00", 1)[0].decode("ascii", "ignore")


def boot_report():
    """Work out why we restarted, log it, update counters. Call once at boot.

    Returns a dict (also used by GET /crash/counter).
    """
    reset_reason = str(microcontroller.cpu.reset_reason).split(".")[-1]
    run_reason = str(supervisor.runtime.run_reason).split(".")[-1]
    last_cause = microcontroller.nvm[NVM_LAST_CAUSE]

    # cpu.reset_reason describes the last *hardware* reset and stays the same
    # across soft reloads (auto-reload on file save, Ctrl-D). Only attribute
    # and count a reset on a real boot, or every reload would be re-counted.
    hard_boot = run_reason == "STARTUP"
    if hard_boot:
        # A watchdog reset can't write NVM itself, so detect it here.
        if reset_reason == "WATCHDOG" and last_cause == CAUSE_NONE:
            last_cause = CAUSE_WATCHDOG
            _bump(CAUSE_WATCHDOG)
        last_self_reset = CAUSE_NAMES.get(last_cause, str(last_cause))
        # Consume the cause so a later plain power-on isn't misattributed.
        microcontroller.nvm[NVM_LAST_CAUSE] = CAUSE_NONE
    else:
        last_self_reset = "n/a (soft reload)"

    report = {
        "reset_reason": reset_reason,
        "run_reason": run_reason,
        "last_self_reset": last_self_reset,
        "last_safe_mode_reason": _safe_mode_reason_from_nvm() or "-",
    }
    logger.log_event(
        f"Boot: cpu.reset_reason={report['reset_reason']}, "
        f"run_reason={report['run_reason']}, "
        f"last self-reset={report['last_self_reset']}, "
        f"last safe-mode reason={report['last_safe_mode_reason']}"
    )
    return report


def counters():
    """Per-cause self-reset counters from NVM (wrap at 255)."""
    return {
        CAUSE_NAMES[c]: microcontroller.nvm[NVM_COUNT_BASE + c - 1]
        for c in (CAUSE_WATCHDOG, CAUSE_STALE, CAUSE_GATEWAY, CAUSE_SAFEMODE, CAUSE_FATAL, CAUSE_STARTUP)
    }


def reset_counters():
    for c in (CAUSE_WATCHDOG, CAUSE_STALE, CAUSE_GATEWAY, CAUSE_SAFEMODE, CAUSE_FATAL, CAUSE_STARTUP):
        microcontroller.nvm[NVM_COUNT_BASE + c - 1] = 0


class HealthMonitor:
    """Watchdog + staleness + gateway checks. Call check() every main-loop pass."""

    def __init__(self):
        self.watchdog_timeout = _setting("TRIX_WATCHDOG_TIMEOUT", 60)   # s, 0 = off
        self.stale_s = _setting("TRIX_STALE_MINUTES", 15) * 60           # 0 = off
        self.stale_after_clear_s = _setting("TRIX_STALE_AFTER_CLEAR_MINUTES", 480) * 60
        self.ping_enabled = _setting("TRIX_GATEWAY_PING", 1) != 0
        self.ping_interval_s = 60
        self.ping_failures_to_reset = 5

        now = time.monotonic()
        self.last_contact = now
        self.allowed_gap = self.stale_after_clear_s  # long grace right after boot
        self.next_ping = now + self.ping_interval_s
        self.ping_armed = False
        self.ping_failures = 0
        self.wdt = None

    def start_watchdog(self):
        """Arm the hardware watchdog. Call early in startup, before Wi-Fi."""
        if self.watchdog_timeout <= 0:
            logger.log_event("Watchdog disabled (TRIX_WATCHDOG_TIMEOUT=0)")
            return
        from watchdog import WatchDogMode
        self.wdt = microcontroller.watchdog
        self.wdt.timeout = self.watchdog_timeout
        self.wdt.mode = WatchDogMode.RESET
        self.wdt.feed()
        logger.log_event(f"Watchdog armed ({self.watchdog_timeout}s)")

    def feed(self):
        if self.wdt is not None:
            self.wdt.feed()

    # Called from route handlers ------------------------------------------
    def record_display(self):
        self.last_contact = time.monotonic()
        self.allowed_gap = self.stale_s

    def record_clear(self):
        self.last_contact = time.monotonic()
        self.allowed_gap = self.stale_after_clear_s

    # Called every main-loop pass ------------------------------------------
    def check(self):
        self.feed()
        now = time.monotonic()

        if self.stale_s > 0 and now - self.last_contact > self.allowed_gap:
            reset_for(CAUSE_STALE, f"(no request for {int(now - self.last_contact)}s)")

        if self.ping_enabled and now >= self.next_ping:
            self.next_ping = now + self.ping_interval_s
            self._ping_gateway()

    def _ping_gateway(self):
        gateway = wifi.radio.ipv4_gateway
        ok = False
        if wifi.radio.connected and gateway is not None:
            try:
                ok = wifi.radio.ping(gateway, timeout=2) is not None
            except Exception:
                ok = False
        self.feed()  # ping can block for up to its timeout

        if ok:
            self.ping_armed = True
            self.ping_failures = 0
            return
        if not self.ping_armed:
            return  # gateway never answered this boot; don't risk a boot loop
        self.ping_failures += 1
        logger.log_event(f"Gateway ping failed ({self.ping_failures}/{self.ping_failures_to_reset})", "WARNING")
        if self.ping_failures >= self.ping_failures_to_reset:
            reset_for(CAUSE_GATEWAY, f"({gateway} unreachable)")
