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

print("MatrixPortal HTTP Server Starting...")

# Initialize ESP32 SPI WiFi
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
radio = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

# Connect to WiFi
print("Connecting to AP...")
while not radio.is_connected:
    try:
        radio.connect_AP(secrets["ssid"], secrets["password"])
    except ConnectionError as e:
        print("could not connect to AP, retrying: ", e)
        continue
print("Connected to", str(radio.ap_info.ssid, "utf-8"), "\tRSSI:", radio.ap_info.rssi)

# Initialize socket pool and requests session
pool = socketpool.SocketPool(radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)
requests = adafruit_requests.Session(pool, ssl_context)

# Initialize display
matrix = Matrix()
color_converter = displayio.ColorConverter(
    input_colorspace=displayio.Colorspace.RGB565,
    dither=True,
)
display_manager = DisplayManager(matrix, color_converter)

# Create application context (shared resources for routes)
context = AppContext(display_manager, requests)

# Run garbage collection before starting server
gc.collect()
print(f"Memory after initialization: {gc.mem_free()} bytes free")

# Create HTTP server and register routes
http_server = Server(pool, debug=False)
routes.register_all(http_server, context)

# Start HTTP server
ip = radio.pretty_ip(radio.ip_address)
print("\n" + "=" * 50)
print(f"Starting HTTP server at {ip}:80")
http_server.start(str(ip), port=80)
print(f"MatrixPortal HTTP Server Ready!")
print("=" * 50)

# Main server loop
print("Listening for HTTP requests...")
while True:
    try:
        http_server.poll()
        # Force GC after each poll cycle to prevent memory buildup
        gc.collect()
    except Exception as e:
        print(f"Server error: {e}")
        gc.collect()  # Also collect on error
        time.sleep(1)
