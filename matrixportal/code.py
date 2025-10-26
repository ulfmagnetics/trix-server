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
color_converter = displayio.ColorConverter(
    input_colorspace=displayio.Colorspace.RGB565,
    dither=True,
)

# Global reference to current TileGrid (for cleanup)
current_face = None

def display_bitmap(bmp):
    """Clear old display and show new bitmap."""
    global current_face

    # CRITICAL: Clear old display FIRST, before creating new TileGrid
    # This ensures we never have both bitmaps in RAM at once
    while len(splash) > 0:
        splash.pop()

    if current_face is not None:
        del current_face
        current_face = None

    # Run garbage collection to free old bitmap/TileGrid
    gc.collect()
    print(f"Memory after clearing old bitmap: {gc.mem_free()} bytes free")

    # Create TileGrid
    new_face = displayio.TileGrid(bmp, pixel_shader=color_converter)

    # Delete bitmap reference (TileGrid holds its own reference)
    del bmp
    gc.collect()

    # Update display
    splash.append(new_face)
    current_face = new_face

    print(f"Memory after displaying bitmap: {gc.mem_free()} bytes free")
    gc.collect()

def load_and_display_bitmap(bitmap_url):
    """Fetch and display a bitmap from the given URL."""
    gc.collect()
    print(f"Memory before load: {gc.mem_free()} bytes free")
    print(f"Fetching bitmap: {bitmap_url}")

    # Start HTTP request
    r = requests.get(bitmap_url)

    # Get content length from headers (pre-allocate exact size)
    content_length = int(r.headers.get('content-length', 0))
    print(f"Content-Length: {content_length} bytes")

    if content_length == 0:
        r.close()
        raise ValueError("No Content-Length header in response")

    # Pre-allocate buffer of exact size (ONE allocation, no fragmentation!)
    print(f"Pre-allocating {content_length} byte buffer...")
    bmp_data = bytearray(content_length)

    # Stream directly into pre-allocated buffer
    offset = 0
    for chunk in r.iter_content(chunk_size=1024):  # Use 1KB chunks
        chunk_len = len(chunk)
        bmp_data[offset:offset+chunk_len] = chunk
        offset += chunk_len

    print(f"Downloaded {offset} bytes")
    r.close()

    # Convert to bytes for utils.bitmap_from_bytes()
    bmp_data = bytes(bmp_data)

    del r
    gc.collect()

    # Parse bitmap
    bmp = utils.bitmap_from_bytes(bmp_data, source_name=bitmap_url)

    # Delete bitmap data immediately after parsing
    del bmp_data
    gc.collect()

    # Display the bitmap (clears old display and creates TileGrid)
    display_bitmap(bmp)

    print(f"Displayed bitmap: {bitmap_url}")

# Don't load default bitmap - save memory for HTTP server
# Display will be blank until first POST request
gc.collect()
print(f"Memory after GC: {gc.mem_free()} bytes free")

# Create HTTP server (debug=False to save memory)
http_server = Server(pool, debug=False)

@http_server.route("/display", methods=["POST"])
def display_bitmap_handler(request: Request):
    """Handle POST requests with bitmap data in body (raw binary)"""
    # Aggressive GC before handling request
    gc.collect()
    print(f"Memory at request start: {gc.mem_free()} bytes free")
    print(f"\nReceived POST request to /display")

    try:
        # Get raw binary data from POST body
        bmp_data = request.body

        if not bmp_data or len(bmp_data) < 138:
            print(f"Invalid or empty bitmap data (size: {len(bmp_data) if bmp_data else 0})")
            return Response(request, "Invalid bitmap data", status=(400, "Bad Request"))

        print(f"Received {len(bmp_data)} bytes of bitmap data")

        # Parse bitmap directly from bytes
        bmp = utils.bitmap_from_bytes(bmp_data, source_name="uploaded")

        # Free bitmap data immediately
        del bmp_data
        gc.collect()

        # Display the bitmap (clears old display and creates TileGrid)
        display_bitmap(bmp)

        print(f"Displayed uploaded bitmap")

        return Response(request, "Bitmap displayed successfully", status=(200, "OK"))

    except Exception as e:
        print(f"Error loading bitmap: {e}")
        return Response(request, f"Error loading bitmap: {e}", status=(500, "Internal Server Error"))

@http_server.route("/fetch", methods=["POST"])
def fetch_bitmap_handler(request: Request):
    """Handle POST requests with bitmap URL in body"""
    # Aggressive GC before handling request
    gc.collect()
    print(f"Memory at request start: {gc.mem_free()} bytes free")
    print(f"\nReceived POST request to /display")

    try:
        # Extract URL from raw POST body
        body_bytes = request.body
        bitmap_url = body_bytes.decode('utf-8', 'ignore').strip()

        # Immediately free body reference
        del body_bytes
        gc.collect()

        if not bitmap_url:
            print("Empty URL in POST body")
            return Response(request, "Empty URL in POST body", status=(400, "Bad Request"))

        print(f"Received URL: {bitmap_url}")

        # Load and display the bitmap
        load_and_display_bitmap(bitmap_url)

        print("Bitmap loaded and displayed successfully")
        return Response(request, "Bitmap displayed successfully", status=(200, "OK"))

    except Exception as e:
        print(f"Error loading bitmap: {e}")
        return Response(request, f"Error loading bitmap: {e}", status=(500, "Internal Server Error"))

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