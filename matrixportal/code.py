# SPDX-FileCopyrightText: 2019 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import adafruit_connection_manager
import adafruit_requests
import board
import busio
import gc
import time
import utils
import displayio

from adafruit_esp32spi import adafruit_esp32spi
from adafruit_matrixportal.matrix import Matrix
from digitalio import DigitalInOut
from adafruit_httpserver import Server, Request, Response
import adafruit_esp32spi.adafruit_esp32spi_socketpool as socketpool

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

print("MatrixPortal HTTP Server Starting...")

# Default bitmap to display on startup
DEFAULT_BITMAP_URL = "https://s3.us-east-1.amazonaws.com/s3.ulfmagnet.com/sketchin/matrix.bmp"

# If you are using a board with pre-defined ESP32 Pins:
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
radio = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

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

# Setup display
matrix = Matrix()
splash = displayio.Group()
matrix.display.root_group = splash

# Color converter for RGB565 bitmaps
color_converter = displayio.ColorConverter(
    input_colorspace=displayio.Colorspace.RGB565,
    dither=True,
)

# Global reference to current TileGrid (for cleanup)
current_face = None

def load_and_display_bitmap(bitmap_url):
    """Fetch and display a bitmap from the given URL."""
    global current_face

    # Free memory before allocation
    gc.collect()
    print(f"Memory before load: {gc.mem_free()} bytes free")

    print(f"Fetching bitmap: {bitmap_url}")

    # Fetch bitmap data
    r = requests.get(bitmap_url)
    bmp_data = r.content
    r.close()
    del r
    gc.collect()

    # Parse bitmap
    bmp = utils.bitmap_from_bytes(bmp_data, source_name=bitmap_url)

    # Delete bitmap data immediately after parsing
    del bmp_data
    gc.collect()

    # Create TileGrid
    new_face = displayio.TileGrid(bmp, pixel_shader=color_converter)

    # Delete bitmap reference (TileGrid holds its own reference)
    del bmp

    # Clear old display and free memory
    while len(splash) > 0:
        splash.pop()

    # Delete old face reference
    if current_face is not None:
        del current_face

    # Run garbage collection to free old bitmap/TileGrid
    gc.collect()

    # Update display with new face
    splash.append(new_face)
    current_face = new_face

    print(f"Displayed bitmap: {bitmap_url}")
    print(f"Memory after load: {gc.mem_free()} bytes free")
    gc.collect()

# Load initial bitmap
print("Loading default bitmap...")
load_and_display_bitmap(DEFAULT_BITMAP_URL)

# Create HTTP server
http_server = Server(pool, debug=True)

@http_server.route("/display", methods=["POST"])
def display_bitmap_handler(request: Request):
    """Handle POST requests with bitmap URL in body"""
    print(f"\nReceived POST request to /display")

    try:
        # Extract URL from raw POST body
        body_bytes = request.body
        bitmap_url = body_bytes.decode('utf-8', errors='ignore').strip()

        if not bitmap_url:
            print("Empty URL in POST body")
            return Response(request, "Empty URL in POST body", status=400)

        print(f"Received URL: {bitmap_url}")

        # Load and display the bitmap
        load_and_display_bitmap(bitmap_url)

        print("Bitmap loaded and displayed successfully")
        return Response(request, "Bitmap displayed successfully", status=200)

    except Exception as e:
        print(f"Error loading bitmap: {e}")
        return Response(request, f"Error loading bitmap: {e}", status=500)

# Start HTTP server
ip = radio.pretty_ip(radio.ip_address)
print("\n" + "=" * 50)
print(f"Starting HTTP server at {ip}:80")
http_server.start(str(ip), port=80)
print(f"MatrixPortal HTTP Server Ready!")
print(f"Test with: curl -X POST http://{ip}/display -d \"<bitmap-url>\"")
print("=" * 50)

# Main server loop
print("Listening for HTTP requests...")
while True:
    try:
        http_server.poll()
    except Exception as e:
        print(f"Server error: {e}")
        time.sleep(1)