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
    print(f"  RSSI: {wifi.radio.ap_info.rssi} dBm")


def initialize_networking_and_server(display_manager):
    """Initialize networking stack and HTTP server.

    Args:
        display_manager: DisplayManager instance

    Returns:
        tuple: (http_server, context) - Server and application context
    """
    # Initialize socket pool and requests session
    pool = socketpool.SocketPool(wifi.radio)
    ssl_context = ssl.create_default_context()
    requests = adafruit_requests.Session(pool, ssl_context)

    # Create application context (no radio parameter needed)
    context = AppContext(display_manager, requests)

    # Create HTTP server and register routes
    http_server = Server(pool, debug=False)

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

# Connect to WiFi (built-in ESP32-S3)
try:
    connect_wifi()
    logger.log_event(f"Connected to WiFi: {os.getenv('CIRCUITPY_WIFI_SSID')}")
except Exception as e:
    logger.log_exception(e, "WiFi connection")
    raise

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
    logger.log_exception(e, "Display initialization")
    raise

# Initialize networking and HTTP server
try:
    gc.collect()
    print(f"Memory after hardware initialization: {gc.mem_free()} bytes free")
    http_server, context = initialize_networking_and_server(display_manager)
    logger.log_event(f"HTTP server ready (free memory: {gc.mem_free()} bytes)")
except Exception as e:
    logger.log_exception(e, "Server initialization")
    raise

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
                # Clear display to remove stale data
                display_manager.clear_display()

                # Reconnect WiFi if disconnected
                if not wifi.radio.connected:
                    print("Reconnecting WiFi...")
                    connect_wifi()

                # Reinitialize server
                http_server, context = initialize_networking_and_server(display_manager)

                print("=" * 50)
                print("Server recovery complete!")
                print("=" * 50)
                logger.log_event("Server recovery successful")

                consecutive_errors = 0  # Reset counter

            except Exception as recovery_error:
                logger.log_exception(recovery_error, "Recovery failed")
                print(f"FATAL: Recovery failed - {recovery_error}")
                # Re-raise to trigger safe mode
                raise

        gc.collect()  # Also collect on error
        time.sleep(1)
