# trix-server

HTTP server for Adafruit MatrixPortal M4 that displays 64x32 bitmaps on an RGB matrix display.

## Features

- **HTTP API** for remote bitmap display control
- **Two display modes:**
  - Upload bitmap data directly via POST
  - Fetch bitmap from URL
- **Memory-efficient** streaming and pre-allocated buffers for stability on embedded hardware
- **Clean architecture** with separated concerns (display, routing, context)

## Project Structure

```
matrixportal/
├── code.py              # Main entry point - WiFi connection & server startup
├── display.py           # DisplayManager class - handles RGB matrix display
├── context.py           # AppContext - dependency injection container
├── utils.py             # Bitmap parsing utilities
├── routes/
│   ├── __init__.py     # Route registration
│   ├── display.py      # /display endpoint (binary upload)
│   └── fetch.py        # /fetch endpoint (URL fetch)
└── secrets.py          # WiFi credentials (not in git)

scripts/
├── deploy.js           # Node.js deployment script

deploy-config.json      # Deployment configuration
```

## Custom Firmware Required

This project requires **custom CircuitPython firmware** with enhanced ESP32SPI library support for server sockets.

### Why Custom Firmware?

The default CircuitPython ESP32SPI library only supports client sockets. This project requires server socket capabilities (`bind()`, `listen()`, `accept()`) which are provided by [Neradoc's PR #218](https://github.com/adafruit/Adafruit_CircuitPython_ESP32SPI/pull/218).

### Building Custom Firmware

1. **Clone CircuitPython repository:**
   ```bash
   git clone https://github.com/adafruit/circuitpython.git
   cd circuitpython
   ```

2. **Install build dependencies:**
   ```bash
   make fetch-submodules
   make fetch-port-submodules BOARD=matrixportal_m4
   ```

3. **Clone enhanced ESP32SPI library:**
   ```bash
   cd frozen/Adafruit_CircuitPython_ESP32SPI
   git fetch origin pull/218/head:more-compatible-api
   git checkout more-compatible-api
   cd ../..
   ```

4. **Build firmware:**
   ```bash
   make BOARD=matrixportal_m4
   ```

5. **Flash to device:**
   - Put MatrixPortal in bootloader mode (double-tap reset button)
   - Copy `build-matrixportal_m4/firmware.uf2` to the MATRIXBOOT drive

### Verifying Custom Firmware

After flashing, run this in the CircuitPython REPL to verify server socket support:

```python
import adafruit_esp32spi.adafruit_esp32spi_socketpool as socketpool
import board, busio, digitalio
from adafruit_esp32spi import adafruit_esp32spi

# Initialize ESP32
esp32_cs = digitalio.DigitalInOut(board.ESP_CS)
esp32_ready = digitalio.DigitalInOut(board.ESP_BUSY)
esp32_reset = digitalio.DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
radio = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

# Check for server socket methods
pool = socketpool.SocketPool(radio)
sock = pool.socket()
print("bind" in dir(sock))      # Should print: True
print("listen" in dir(sock))    # Should print: True
print("accept" in dir(sock))    # Should print: True
```

## Getting Started

### Prerequisites

- Adafruit MatrixPortal M4 with custom CircuitPython firmware (see above)
- 64x32 RGB LED matrix panel
- Node.js installed on your development machine
- WiFi network credentials

### Setup

1. **Create WiFi secrets file** at `matrixportal/secrets.py`:
   ```python
   secrets = {
       "ssid": "your-wifi-ssid",
       "password": "your-wifi-password"
   }
   ```

   > **Note:** This file is gitignored and must be created manually

2. **Connect your MatrixPortal** via USB
   - It should mount as a drive (default: E:)
   - If it mounts to a different drive letter, update `deploy-config.json`

3. **Deploy to your device:**
   ```bash
   npm run deploy
   ```
   - Copies all files from `matrixportal/` to your MatrixPortal
   - Device automatically resets and runs the new code

4. **Find your device IP:**
   - Connect to the serial console to see the IP address printed on startup
   - Use a serial monitor like Mu Editor, PuTTY, or Arduino Serial Monitor

## API Documentation

### Base URL

```
http://<MATRIXPORTAL_IP>:80
```

The MatrixPortal IP address is printed to the serial console on startup.

### POST /display

Upload bitmap data directly to the display.

**Request:**
- **Method:** `POST`
- **Content-Type:** `application/octet-stream`
- **Body:** Raw BMP file data (must be 64x32, 24-bit RGB)

**Response:**
- **200 OK:** `"Bitmap displayed successfully"`
- **400 Bad Request:** Invalid or empty bitmap data
- **500 Internal Server Error:** Error during bitmap processing

**Example:**
```bash
# Upload a local bitmap file
curl -X POST http://192.168.1.126/display \
  --data-binary @my-bitmap.bmp \
  -H "Content-Type: application/octet-stream"
```

**Memory:** Most efficient option - uses ~6KB peak memory

### POST /fetch

Fetch and display a bitmap from a URL.

**Request:**
- **Method:** `POST`
- **Content-Type:** `text/plain`
- **Body:** URL string pointing to a BMP file

**Response:**
- **200 OK:** `"Bitmap displayed successfully"`
- **400 Bad Request:** Empty URL in POST body
- **500 Internal Server Error:** Error during download or processing

**Example:**
```bash
# Fetch from URL
curl -X POST http://192.168.1.126/fetch \
  -d "https://example.com/images/bitmap.bmp"
```

**Memory:** Requires pre-allocated buffer matching bitmap file size

## Bitmap Requirements

- **Dimensions:** 64x32 pixels (width x height)
- **Format:** BMP (Windows Bitmap)
- **Color Depth:** 24-bit RGB
- **File Size:** ~6KB typical

### Creating Compatible Bitmaps

Using ImageMagick:
```bash
convert input.png -resize 64x32! -type truecolor BMP3:output.bmp
```

Using Python (PIL):
```python
from PIL import Image
img = Image.open("input.png")
img = img.resize((64, 32))
img = img.convert("RGB")
img.save("output.bmp", "BMP")
```

## Development Workflow

1. **Edit your code** in the `matrixportal/` directory
2. **Deploy changes:**
   ```bash
   npm run deploy
   ```
3. **Monitor serial output** to see logs and debug information
4. **Test API endpoints** using curl or HTTP client

## Memory Management

The MatrixPortal M4 has only **192KB of RAM**. This implementation uses several strategies to avoid memory allocation failures:

- **Pre-allocated buffers** for HTTP downloads (single allocation, no fragmentation)
- **Clear old display BEFORE loading new bitmap** (never hold two bitmaps in RAM)
- **Aggressive garbage collection** after each operation
- **Streaming downloads** in 1KB chunks
- **Immediate cleanup** of temporary objects

Typical memory profile:
- **Startup:** ~79KB free
- **After displaying bitmap:** ~69KB free
- **Stable across 6+ consecutive requests**

## Troubleshooting

### Device won't connect to WiFi
- Check `secrets.py` credentials are correct
- Verify WiFi network is 2.4GHz (ESP32 doesn't support 5GHz)
- Check serial console for connection error messages

### Memory allocation errors
- Ensure only one bitmap is in RAM at a time
- Check bitmap file size (should be ~6KB for 64x32x24bit)
- Monitor serial console for memory free reports

### Server socket errors
- Verify custom firmware is installed (see "Verifying Custom Firmware")
- Check that `bind`, `listen`, `accept` methods exist on Socket objects
- Ensure ESP32 SPI connections are correct

### Bitmap doesn't display
- Verify bitmap is exactly 64x32 pixels
- Check bitmap is 24-bit RGB format (not indexed color)
- Monitor serial console for parsing errors

## Contributing

This is an embedded device project with strict memory constraints. When contributing:

1. **Test memory usage** - Monitor `gc.mem_free()` before/after changes
2. **Pre-allocate buffers** - Avoid multiple small allocations
3. **Clean up immediately** - Delete temporary objects and call `gc.collect()`
4. **Test multiple requests** - Ensure no memory leaks across 6+ requests

## License

SPDX-License-Identifier: MIT
