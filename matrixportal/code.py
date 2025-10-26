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

# Initialize a requests session
pool = adafruit_connection_manager.get_radio_socketpool(radio)
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

# Print IP address for testing
print("=" * 50)
print(f"MatrixPortal HTTP Server Ready!")
print(f"IP Address: {radio.pretty_ip(radio.ip_address)}")
print(f"Test with: curl -X POST http://{radio.pretty_ip(radio.ip_address)} -d \"<bitmap-url>\"")
print("=" * 50)

# Create HTTP server using ESP32 SPI API
print("Creating server socket...")
socket_num = radio.get_socket()
print(f"Allocated socket number: {socket_num}")

# Start server on port 80
radio.start_server(port=80, socket_num=socket_num)
print(f"Server started on port 80, socket {socket_num}")

# Verify server is listening
state = radio.server_state(socket_num)
print(f"Server state: {state}")
print("Listening for HTTP requests on port 80...")

# Socket state constants
SOCKET_CLOSED = 0
SOCKET_LISTEN = 1
SOCKET_ESTABLISHED = 4

# Buffer for accumulating request data
request_buffer = b""

# Main server loop - poll for incoming connections
print("Waiting for client connections...")
while True:
    try:
        # Check the server socket state
        state = radio.server_state(socket_num)

        # Only process data if a client is connected (SOCKET_ESTABLISHED)
        if state != SOCKET_ESTABLISHED:
            # No client connected, continue polling
            time.sleep(0.1)
            continue

        # Client is connected! Check if data is available
        available = radio.socket_available(socket_num)

        if available <= 0:
            # No data available yet, continue polling
            time.sleep(0.05)
            continue

        # Data available - read it
        print(f"\nClient connected, reading {available} bytes...")
        chunk = radio.socket_read(socket_num, available)
        request_buffer += chunk

        # Check if we have complete headers
        if b"\r\n\r\n" not in request_buffer:
            # Wait for more data if headers are incomplete
            continue

        # We have a complete HTTP request (headers + body)
        print(f"Received request ({len(request_buffer)} bytes)")

        try:
            # Parse HTTP request
            request_str = request_buffer.decode('utf-8', errors='ignore')
            lines = request_str.split('\r\n')

            # Check if it's a POST request
            if lines[0].startswith('POST'):
                # Find Content-Length header
                content_length = 0
                for line in lines:
                    if line.lower().startswith('content-length:'):
                        content_length = int(line.split(':')[1].strip())
                        break

                # Extract body
                header_end = request_buffer.find(b"\r\n\r\n")
                body = request_buffer[header_end + 4:]

                # Check if we have the complete body
                if len(body) >= content_length:
                    # Extract URL from body
                    bitmap_url = body[:content_length].decode('utf-8', errors='ignore').strip()

                    if bitmap_url:
                        print(f"Received URL: {bitmap_url}")

                        try:
                            # Load and display the bitmap
                            load_and_display_bitmap(bitmap_url)

                            # Send success response
                            response = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nBitmap displayed successfully\r\n"
                            radio.socket_write(socket_num, response)
                            print("Bitmap loaded and displayed successfully")

                        except Exception as e:
                            print(f"Error loading bitmap: {e}")
                            response = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nError loading bitmap: {e}\r\n".encode()
                            radio.socket_write(socket_num, response)
                    else:
                        print("Empty URL in POST body")
                        response = b"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nEmpty URL in POST body\r\n"
                        radio.socket_write(socket_num, response)

                    # Clear buffer for next request
                    request_buffer = b""
            else:
                # Not a POST request
                print(f"Not a POST request: {lines[0]}")
                response = b"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOnly POST requests are supported\r\n"
                radio.socket_write(socket_num, response)
                request_buffer = b""

        except Exception as e:
            print(f"Error parsing request: {e}")
            response = b"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nError processing request\r\n"
            try:
                radio.socket_write(socket_num, response)
            except:
                pass
            request_buffer = b""

            gc.collect()

        # Small delay to prevent busy-waiting
        time.sleep(0.1)

    except Exception as e:
        print(f"Server error: {e}")
        request_buffer = b""
        time.sleep(1)