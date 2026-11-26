# SPDX-FileCopyrightText: 2019 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""MatrixPortal HTTP Server - Main entry point."""

import adafruit_requests
import displayio
import gc
import os
import socketpool
import ssl
import time
import wifi
from adafruit_httpserver import Server
from adafruit_matrixportal.matrix import Matrix

from display import DisplayManager
from context import AppContext
from crash_logger import logger
import health
import routes


def connect_wifi():
    """Connect to WiFi using credentials from settings.toml."""
    ssid = os.getenv('CIRCUITPY_WIFI_SSID')
    password = os.getenv('CIRCUITPY_WIFI_PASSWORD')

    if not ssid or not password:
        raise ValueError(
            "WiFi credentials not found. Create settings.toml with:\n"
            "CIRCUITPY_WIFI_SSID = \"your-network\"\n"
            "CIRCUITPY_WIFI_PASSWORD = \"your-password\""
        )

    print(f"Connecting to WiFi: {ssid}")
    while not wifi.radio.connected:
        try:
            wifi.radio.connect(ssid, password)
        except ConnectionError as e:
            print(f"  Could not connect, retrying: {e}")
            time.sleep(1)

    print(f"Connected to {ssid}")
    print(f"  IP: {wifi.radio.ipv4_address}")
    if wifi.radio.ap_info:
        print(f"  RSSI: {wifi.radio.ap_info.rssi} dBm")


def load_api_key():
    """Load API key from settings.toml with fail-secure validation."""
    api_key = os.getenv('TRIX_API_KEY')

    if not api_key:
        raise ValueError(
            "API key not configured. Add to settings.toml:\n"
            "TRIX_API_KEY = \"your-secure-random-key\""
        )

    if len(api_key) < 16:
        raise ValueError(
            "API key too short (minimum 16 characters required). "
            "Generate a secure random key for TRIX_API_KEY in settings.toml"
        )

    print("API key loaded (authentication enabled)")
    return api_key


def initialize_networking_and_server(display_manager, api_key):
    """Initialize networking stack and HTTP server.

    Args:
        display_manager: DisplayManager instance
        api_key: API key for authentication

    Returns:
        tuple: (http_server, context) - Server and application context
    """
    # Initialize socket pool and requests session
    pool = socketpool.SocketPool(wifi.radio)
    ssl_context = ssl.create_default_context()
    requests = adafruit_requests.Session(pool, ssl_context)

    # Create application context
    context = AppContext(display_manager, requests, api_key, monitor)
    context.boot_info = boot_info  # reported by GET /crash/counter

    # Create HTTP server and register routes
    http_server = Server(pool, debug=False)  # type: ignore[arg-type]

    # Configure server for reliable large POST requests (6198-byte bitmaps)
    # Default buffer (1024 bytes) requires ~6 recv() calls, increasing timeout risk
    http_server.request_buffer_size = 8192  # Reduces to 1-2 recv() calls
    http_server.socket_timeout = 3  # Increased from 1s to handle network latency

    routes.register_all(http_server, context)

    # Start HTTP server
    ip = wifi.radio.ipv4_address
    http_server.start(str(ip), port=80)
    print(f"HTTP server started at {ip}:80")

    return http_server, context


print("MatrixPortal HTTP Server Starting...")
logger.log_event("MatrixPortal HTTP Server Starting")

# Why did we (re)start? Reads/updates the reset bookkeeping in NVM.
boot_info = health.boot_report()
monitor = health.HealthMonitor()

# Arm the watchdog before anything that can hang (Wi-Fi join, server start).
# If startup stalls for longer than the timeout, the board resets and retries.
monitor.start_watchdog()

STARTUP_RETRY_DELAY = 30  # seconds to wait before resetting after a startup error


def startup_failed(stage, error):
    """Log a startup error, then reset instead of dropping to the REPL.

    CircuitPython disarms the watchdog when code.py exits, so without this a
    startup exception would leave the board at "Code done running" until
    someone pressed reset. The delay keeps the error readable on the serial
    console and stops a persistent fault (e.g. a bad settings.toml) from
    reset-looping fast.
    """
    logger.log_exception(error, stage)
    print(f"Startup failed during {stage}; resetting in {STARTUP_RETRY_DELAY}s")
    end = time.monotonic() + STARTUP_RETRY_DELAY
    while time.monotonic() < end:
        monitor.feed()
        time.sleep(1)
    health.reset_for(health.CAUSE_STARTUP, f"({stage}: {error})")

# Connect to WiFi (built-in ESP32-S3)
try:
    connect_wifi()
    logger.log_event(f"Connected to WiFi: {os.getenv('CIRCUITPY_WIFI_SSID')}")
except Exception as e:
    startup_failed("WiFi connection", e)

# Load API key (fail-secure - must be configured)
try:
    api_key = load_api_key()
    logger.log_event("API key loaded successfully")
except Exception as e:
    startup_failed("API key loading", e)

# Initialize display
try:
    matrix = Matrix()
    color_converter = displayio.ColorConverter(
        input_colorspace=displayio.Colorspace.RGB565,
        dither=True,
    )
    display_manager = DisplayManager(matrix, color_converter)
    logger.log_event("Display initialized")
except Exception as e:
    startup_failed("Display initialization", e)

# Initialize networking and HTTP server
try:
    gc.collect()
    print(f"Memory after hardware initialization: {gc.mem_free()} bytes free")  # type: ignore[attr-defined]
    http_server, context = initialize_networking_and_server(display_manager, api_key)
    logger.log_event(f"HTTP server ready (free memory: {gc.mem_free()} bytes)")  # type: ignore[attr-defined]
except Exception as e:
    startup_failed("Server initialization", e)

print("=" * 50)
print(f"MatrixPortal HTTP Server Ready!")
print("=" * 50)

# Main server loop
print("Listening for HTTP requests w/ automatic error recovery...")
logger.log_event("Entering main server loop")
consecutive_errors = 0
ERROR_THRESHOLD = 3

while True:
    try:
        # Feed watchdog; reset if trix-hub has gone quiet or the gateway is gone
        monitor.check()
        # Force GC BEFORE poll to defragment memory for incoming requests
        gc.collect()
        http_server.poll()
        consecutive_errors = 0  # Reset on success
        # Force GC after each poll cycle to prevent memory buildup
        gc.collect()
    except Exception as e:
        print(f"Server error: {e}")
        logger.log_exception(e, f"Server poll (error #{consecutive_errors + 1})")
        consecutive_errors += 1

        if consecutive_errors >= ERROR_THRESHOLD:
            print(f"\nServer unresponsive after {consecutive_errors} errors, attempting recovery...")
            logger.log_event(f"Recovery triggered: consecutive errors ({consecutive_errors})", "WARNING")

            try:
                monitor.feed()
                # Clear display to remove stale data
                display_manager.clear_display()

                # Reconnect WiFi if disconnected
                if not wifi.radio.connected:
                    print("Reconnecting WiFi...")
                    connect_wifi()

                # Reinitialize server
                http_server, context = initialize_networking_and_server(display_manager, api_key)

                print("=" * 50)
                print("Server recovery complete!")
                print("=" * 50)
                logger.log_event("Server recovery successful")

                consecutive_errors = 0  # Reset counter

            except Exception as recovery_error:
                logger.log_exception(recovery_error, "Recovery failed")
                print(f"FATAL: Recovery failed - {recovery_error}")
                # Reset instead of exiting to the REPL, where the board would
                # sit until someone pressed the reset button.
                health.reset_for(health.CAUSE_FATAL, f"(recovery failed: {recovery_error})")

        gc.collect()  # Also collect on error
        time.sleep(1)
