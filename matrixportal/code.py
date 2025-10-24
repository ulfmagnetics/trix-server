# SPDX-FileCopyrightText: 2019 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import adafruit_connection_manager
import board
import busio
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_matrixportal.matrix import Matrix
from adafruit_matrixportal.graphics import Graphics
from digitalio import DigitalInOut

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

BITMAP_URL = "https://s3.amazonaws.com/s3.ulfmagnet.com/sketchin/sir_of_being_on_fire_64x32.bmp"

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
    except RuntimeError as e:
        print("could not connect to AP, retrying: ", e)
        continue
print("Connected to", str(radio.ap_info.ssid, "utf-8"), "\tRSSI:", radio.ap_info.rssi)

# Initialize a requests session
pool = adafruit_connection_manager.get_radio_socketpool(radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)
requests = adafruit_requests.Session(pool, ssl_context)

utils.dump_mem_usage()

image_path = "/images/current.bmp"
print("Fetching bitmap from", BITMAP_URL)
r = requests.get(BITMAP_URL)
with open(image_path, mode='wb') as f:
    f.write(r.content)
# bitmap_data = r.content
r.close()

utils.dump_mem_usage()

# TODO: read the bitmap from memory, create palette, write pixels
print("displaying...")
# matrix = Matrix()
# splash = displayio.Group()
# bmp = displayio.Bitmap(64, 32, 256)
# fill_region(bmp, 10, 10, 44, 30, 180)
# color_converter = displayio.ColorConverter(
#     input_colorspace=displayio.Colorspace.RGB565_SWAPPED,
#     dither=True,
# )
# face = displayio.TileGrid(bmp, pixel_shader=color_converter)
# splash.append(face)
# matrix.display.root_group = splash
# odb = displayio.OnDiskBitmap(image_path)
# tile_grid = displayio.TileGrid(odb, pixel_shader=odb.pixel_shader)
# splash.append(tile_grid)
# matrix.display.root_group = splash
print("displayed")

while True:
    pass