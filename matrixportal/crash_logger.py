# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""Crash logging system for MatrixPortal M4.

Provides persistent crash logging with filesystem, NVM, and memory buffer fallback.
Captures full stack traces, uptime, and crash counts for debugging random crashes.
"""

import time
import traceback
import microcontroller
import supervisor
import gc


class CrashLogger:
    """Hybrid crash logger with file, NVM, and memory buffer support."""

    def __init__(self, log_file="/crash.log", max_memory_logs=50):
        """Initialize crash logger.

        Args:
            log_file: Path to log file on filesystem
            max_memory_logs: Maximum events to buffer in memory when filesystem unavailable
        """
        self.log_file = log_file
        self.boot_time = time.monotonic()
        self.crash_count = microcontroller.nvm[0]
        self.memory_buffer = []
        self.max_memory_logs = max_memory_logs

        # Increment crash counter in NVM (persists across power cycles)
        microcontroller.nvm[0] = (self.crash_count + 1) & 0xFF

        # Log boot information
        self._log_boot()

    def _log_boot(self):
        """Log boot information including crash count and run reason."""
        msg = f"\n{'='*60}\n"
        msg += f"BOOT at {time.monotonic():.2f}s\n"
        msg += f"Crash count: {self.crash_count}\n"
        msg += f"Run reason: {supervisor.runtime.run_reason}\n"
        msg += f"USB connected: {supervisor.runtime.usb_connected}\n"
        msg += f"Serial connected: {supervisor.runtime.serial_connected}\n"
        msg += f"Free memory: {gc.mem_free()} bytes\n"
        msg += f"{'='*60}\n"
        self._write(msg)

    def _get_uptime(self):
        """Get uptime in seconds since boot."""
        return time.monotonic() - self.boot_time

    def _write(self, message):
        """Try to write to file, fallback to memory buffer if filesystem unavailable.

        Args:
            message: String to write

        Returns:
            bool: True if written to file, False if buffered in memory
        """
        try:
            with open(self.log_file, "a") as f:
                f.write(message)
            return True
        except OSError:
            # Filesystem read-only or full - buffer in memory
            self.memory_buffer.append(message)
            if len(self.memory_buffer) > self.max_memory_logs:
                self.memory_buffer.pop(0)  # Remove oldest
            return False

    def log_event(self, message, level="INFO"):
        """Log an event with timestamp and level.

        Args:
            message: Event message
            level: Log level (INFO, WARNING, ERROR)
        """
        uptime = self._get_uptime()
        log_msg = f"[{uptime:08.2f}] {level}: {message}\n"

        # Also print to console if serial connected
        if supervisor.runtime.serial_connected:
            print(log_msg.strip())

        self._write(log_msg)

    def log_exception(self, exception, context=""):
        """Log exception with full stack trace.

        Args:
            exception: Exception instance
            context: Additional context string (e.g., "HTTP /display handler")
        """
        uptime = self._get_uptime()

        msg = f"\n{'='*60}\n"
        msg += f"EXCEPTION at {uptime:.2f}s\n"
        if context:
            msg += f"Context: {context}\n"
        msg += f"Type: {type(exception).__name__}\n"
        msg += f"Message: {exception}\n"
        msg += f"Free memory: {gc.mem_free()} bytes\n"
        msg += "-" * 60 + "\n"

        # Get full traceback
        try:
            trace_lines = traceback.format_exception(exception)
            msg += ''.join(trace_lines)
        except Exception as e:
            msg += f"Failed to get traceback: {e}\n"

        msg += "=" * 60 + "\n"

        # Print to console if connected
        if supervisor.runtime.serial_connected:
            print(msg)

        self._write(msg)

    def log_esp32_reset(self, reason=""):
        """Log ESP32 reset event.

        Args:
            reason: Reason for reset (e.g., "consecutive errors", "manual")
        """
        self.log_event(f"ESP32 reset triggered - {reason}", "WARNING")

    def dump_memory_buffer(self):
        """Try to dump memory buffer to file (call when filesystem becomes writable).

        Returns:
            bool: True if successfully dumped, False otherwise
        """
        if not self.memory_buffer:
            return True

        try:
            with open(self.log_file, "a") as f:
                f.write("\n=== MEMORY BUFFER DUMP ===\n")
                for entry in self.memory_buffer:
                    f.write(entry)
                f.write("=== END BUFFER ===\n")
            self.memory_buffer.clear()
            return True
        except OSError:
            return False

    def reset_crash_counter(self):
        """Reset the persistent crash counter in NVM.

        Call this after a successful period of operation to clear the counter.
        """
        microcontroller.nvm[0] = 0
        self.crash_count = 0
        self.log_event("Crash counter reset", "INFO")

    def get_log_contents(self, max_lines=None):
        """Read and return crash log contents.

        Args:
            max_lines: Maximum number of lines to return (None = all)

        Returns:
            str: Log file contents, or error message if unavailable
        """
        try:
            with open(self.log_file, "r") as f:
                if max_lines is None:
                    return f.read()
                else:
                    lines = f.readlines()
                    return ''.join(lines[-max_lines:])
        except OSError as e:
            return f"Error reading log file: {e}"

    def clear_log(self):
        """Clear the crash log file.

        Returns:
            bool: True if successfully cleared, False otherwise
        """
        try:
            with open(self.log_file, "w") as f:
                f.write(f"Log cleared at {self._get_uptime():.2f}s\n")
            return True
        except OSError:
            return False


# Global logger instance (initialized on import)
logger = CrashLogger()
