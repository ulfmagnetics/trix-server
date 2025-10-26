# SPDX-FileCopyrightText: 2019 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import adafruit_connection_manager
import board
import busio
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_matrixportal.matrix import Matrix
from adafruit_matrixportal.graphics import Graphics
from digitalio import DigitalInOut, Direction, Pull
import time

import utils
import displayio
from bitmaptools import fill_region
import adafruit_requests

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

print("ESP32 SPI webclient test!")

# BITMAP_URL = "https://s3.amazonaws.com/s3.ulfmagnet.com/sketchin/sir_of_being_on_fire_64x32.bmp"
# BITMAP_URL = "https://s3.us-east-1.amazonaws.com/s3.ulfmagnet.com/sketchin/matrix.bmp"
BITMAP_URLS = [
    "https://s3.us-east-1.amazonaws.com/s3.ulfmagnet.com/sketchin/just-red.bmp", # displays as blue
    "https://s3.us-east-1.amazonaws.com/s3.ulfmagnet.com/sketchin/just-green.bmp", # display as green
    "https://s3.us-east-1.amazonaws.com/s3.ulfmagnet.com/sketchin/just-blue.bmp", # displays as blue
]

# If you are using a board with pre-defined ESP32 Pins:
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)

# Configure buttons
button_up = DigitalInOut(board.BUTTON_UP)
button_up.direction = Direction.INPUT
button_up.pull = Pull.UP

button_down = DigitalInOut(board.BUTTON_DOWN)
button_down.direction = Direction.INPUT
button_down.pull = Pull.UP

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

def load_and_display_bitmap(index):
    """Fetch and display a bitmap from BITMAP_URLS[index]."""
    bitmap_url = BITMAP_URLS[index]
    print(f"Fetching bitmap {index}: {bitmap_url}")

    # Fetch bitmap data
    r = requests.get(bitmap_url)
    bmp_data = r.content
    r.close()

    # Parse bitmap
    bmp = utils.bitmap_from_bytes(bmp_data, source_name=bitmap_url)

    # Create TileGrid
    face = displayio.TileGrid(bmp, pixel_shader=color_converter)

    # Update display
    while len(splash) > 0:
        splash.pop()
    splash.append(face)

    print(f"Displayed bitmap {index}")

# Track current bitmap index
current_index = 0

# Load initial bitmap
print("Loading initial bitmap...")
load_and_display_bitmap(current_index)

# Main loop - handle button presses
while True:
    # Check button_up (pressed = False due to pull-up)
    if not button_up.value:
        current_index = (current_index + 1) % len(BITMAP_URLS)
        print(f"Button UP pressed - switching to index {current_index}")
        load_and_display_bitmap(current_index)
        time.sleep(0.3)  # Debounce delay

    # Check button_down (pressed = False due to pull-up)
    if not button_down.value:
        current_index = (current_index - 1) % len(BITMAP_URLS)
        print(f"Button DOWN pressed - switching to index {current_index}")
        load_and_display_bitmap(current_index)
        time.sleep(0.3)  # Debounce delay

    time.sleep(0.1)  # Small delay to prevent busy-waiting