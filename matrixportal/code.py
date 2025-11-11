# SPDX-FileCopyrightText: 2019 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""MatrixPortal HTTP Server - Main entry point."""

import adafruit_connection_manager
import adafruit_requests
import board
import busio
import gc
import time
import displayio
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_matrixportal.matrix import Matrix
from digitalio import DigitalInOut
from adafruit_httpserver import Server
import adafruit_esp32spi.adafruit_esp32spi_socketpool as socketpool

from display import DisplayManager
from context import AppContext
import routes

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

def connect_wifi(radio, wifi_secrets):
    """Connect to WiFi access point.

    Args:
        radio: ESP_SPIcontrol instance
        wifi_secrets: Dictionary with 'ssid' and 'password' keys
    """
    print("Connecting to AP...")
    while not radio.is_connected:
        try:
            radio.connect_AP(wifi_secrets["ssid"], wifi_secrets["password"])
        except ConnectionError as e:
            print(f"  Could not connect to AP, retrying: {e}")
            time.sleep(1)
    print("Connected to", str(radio.ap_info.ssid, "utf-8"), "\tRSSI:", radio.ap_info.rssi)


def initialize_networking_and_server(radio, display_manager):
    """Initialize networking stack and HTTP server.

    Args:
        radio: ESP_SPIcontrol instance
        display_manager: DisplayManager instance

    Returns:
        tuple: (http_server, context) - Server and application context
    """
    # Initialize socket pool and requests session
    pool = socketpool.SocketPool(radio)
    ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)
    requests = adafruit_requests.Session(pool, ssl_context)

    # Create application context (shared resources for routes)
    context = AppContext(display_manager, requests, radio)

    # Create HTTP server and register routes
    http_server = Server(pool, debug=False)
    routes.register_all(http_server, context)

    # Start HTTP server
    ip = radio.pretty_ip(radio.ip_address)
    http_server.start(str(ip), port=80)
    print(f"HTTP server started at {ip}:80")

    return http_server, context


print("MatrixPortal HTTP Server Starting...")

# Initialize ESP32 SPI WiFi hardware
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
radio = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

# Connect to WiFi
connect_wifi(radio, secrets)

# Initialize display
matrix = Matrix()
color_converter = displayio.ColorConverter(
    input_colorspace=displayio.Colorspace.RGB565,
    dither=True,
)
display_manager = DisplayManager(matrix, color_converter)

# Initialize networking and HTTP server
gc.collect()
print(f"Memory after hardware initialization: {gc.mem_free()} bytes free")
http_server, context = initialize_networking_and_server(radio, display_manager)

print("=" * 50)
print(f"MatrixPortal HTTP Server Ready!")
print("=" * 50)

# Main server loop
print("Listening for HTTP requests w/ automatic error recovery...")
consecutive_errors = 0
ERROR_THRESHOLD = 3

while True:
    try:
        http_server.poll()
        consecutive_errors = 0  # Reset on success
        # Force GC after each poll cycle to prevent memory buildup
        gc.collect()
    except Exception as e:
        print(f"Server error: {e}")
        consecutive_errors += 1

        if consecutive_errors >= ERROR_THRESHOLD:
            print(f"\nESP32 unresponsive after {consecutive_errors} errors, performing hardware reset...")

            # Clear display to remove stale data
            display_manager.clear_display()

            # Reset ESP32 using built-in method
            print("Resetting ESP32...")
            radio.reset()
            time.sleep(2)  # Wait for ESP32 boot

            # Reconnect WiFi and reinitialize server
            connect_wifi(radio, secrets)
            http_server, context = initialize_networking_and_server(radio, display_manager)

            print("=" * 50)
            print("Server recovery complete!")
            print("=" * 50)

            consecutive_errors = 0  # Reset counter

        gc.collect()  # Also collect on error
        time.sleep(1)
