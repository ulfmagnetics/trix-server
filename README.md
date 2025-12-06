# trix-server

HTTP server for Adafruit MatrixPortal S3 that displays 64x32 bitmaps on an RGB matrix display.

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
├── code.py                  # Main entry point - WiFi connection & server startup
├── boot.py                  # Boot configuration - filesystem write permissions
├── display.py               # DisplayManager class - handles RGB matrix display
├── context.py               # AppContext - dependency injection container
├── crash_logger.py          # Hybrid crash logging system (file/NVM/memory)
├── utils.py                 # Bitmap parsing utilities
├── routes/
│   ├── __init__.py         # Route registration
│   ├── display.py          # /display endpoint (binary upload)
│   ├── fetch.py            # /fetch endpoint (URL fetch)
│   ├── clear.py            # /clear endpoint (clear display)
│   └── crash.py            # /crash endpoints (logging and diagnostics)
├── settings.toml.example    # WiFi credentials template
└── settings.toml            # WiFi credentials (not in git, create from example)

scripts/
├── deploy.js                # Node.js deployment script

build.sh                     # mpy-cross compilation script
deploy-config.json           # Deployment configuration
```

## Hardware Architecture

The MatrixPortal S3 features:
- **ESP32-S3** processor with built-in WiFi (no SPI co-processor needed)
- **Hardware parallel output peripheral** for matrix control (faster than M4 bitbanging)
- **Dual-core architecture** - one core for WiFi/matrix, one for your code
- **8MB flash, 2MB PSRAM** - significantly more memory than the M4's 192KB RAM

**No custom firmware required** - standard CircuitPython works out of the box!

## Getting Started

### Prerequisites

- Adafruit MatrixPortal S3 with CircuitPython 9.0+ installed
- 64x32 RGB LED matrix panel (or other HUB-75 compatible sizes)
- Node.js installed on your development machine
- WiFi network (2.4GHz or 5GHz)
- WSL (Windows Subsystem for Linux) for mpy-cross compilation (optional but recommended)

### Setup

1. **Create WiFi settings file** on the CIRCUITPY drive:

   Copy `matrixportal/settings.toml.example` to the CIRCUITPY drive and rename it to `settings.toml`:

   ```toml
   # WiFi credentials for MatrixPortal S3
   CIRCUITPY_WIFI_SSID = "your-network-name"
   CIRCUITPY_WIFI_PASSWORD = "your-password"

   # Disable CircuitPython web workflow (allows our HTTP server to use port 80)
   CIRCUITPY_WEB_API_PASSWORD = ""
   ```

   > **Important:**
   > - This file must be on the CIRCUITPY drive, not in the git repository
   > - Set `CIRCUITPY_WEB_API_PASSWORD = ""` to disable the built-in web server
   > - Without this, you'll get an `EADDRINUSE` error (port 80 conflict)

2. **Connect your MatrixPortal** via USB
   - It should mount as a drive (default: E:)
   - If it mounts to a different drive letter, update `deploy-config.json`

3. **Deploy to your device:**
   ```bash
   npm run deploy
   ```
   - Compiles Python modules to `.mpy` bytecode using mpy-cross
   - Copies compiled modules and non-compiled files to CIRCUITPY drive
   - Device automatically resets and runs the new code
   - Provides 9-14 KB memory savings vs raw `.py` files

4. **Find your device IP:**
   - Connect to the serial console to see the IP address printed on startup
   - Use a serial monitor like Mu Editor, PuTTY, or Arduino Serial Monitor

   Expected startup output:
   ```
   Connecting to WiFi: YourNetwork
   Connected to YourNetwork
     IP: 192.168.1.XXX
     RSSI: -XX dBm
   HTTP server started at 192.168.1.XXX:80
   ```

5. **(Optional) Set static IP:**
   - Find your device's MAC address (see "Finding MAC Address" below)
   - Configure DHCP reservation in your router using the MAC address

## Finding MAC Address

To set a static IP reservation in your router, you'll need the MatrixPortal's MAC address:

**Method 1: Serial Console**
```python
import wifi
print("MAC:", ":".join([f"{b:02X}" for b in wifi.radio.mac_address]))
```

**Method 2: Add to code.py**

Add after WiFi connection (around line 90):
```python
mac_bytes = wifi.radio.mac_address
mac_str = ":".join([f"{b:02X}" for b in mac_bytes])
print(f"  MAC: {mac_str}")
```

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
curl -X POST http://192.168.1.XXX/display \
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
curl -X POST http://192.168.1.XXX/fetch \
  -d "https://example.com/images/bitmap.bmp"
```

**Memory:** Requires pre-allocated buffer matching bitmap file size

### GET /clear

Clear the display (all pixels off).

**Request:**
- **Method:** `GET`

**Response:**
- **200 OK:** `"Display cleared"`
- **500 Internal Server Error:** Error during clear operation

**Example:**
```bash
curl http://192.168.1.XXX/clear
```

### GET /crash

View crash logs and diagnostics.

**Request:**
- **Method:** `GET`

**Response:**
- **200 OK:** Crash log contents (text/plain)

**Example:**
```bash
curl http://192.168.1.XXX/crash
```

### POST /crash/clear

Clear the crash log file.

**Request:**
- **Method:** `POST`

**Response:**
- **200 OK:** `"Crash log cleared"`
- **500 Internal Server Error:** Failed to clear log

**Example:**
```bash
curl -X POST http://192.168.1.XXX/crash/clear
```

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

The MatrixPortal S3 has **2MB of PSRAM** - significantly more than the M4's 192KB. However, this implementation still uses memory-efficient strategies:

- **Pre-allocated buffers** for HTTP downloads (single allocation, no fragmentation)
- **Clear old display BEFORE loading new bitmap** (never hold two bitmaps in RAM)
- **Aggressive garbage collection** after each operation
- **Streaming downloads** in 1KB chunks
- **Compiled `.mpy` modules** (37% smaller than `.py`, 9-14 KB RAM savings)

Typical memory profile (with `.mpy` modules):
- **Startup:** ~1.9 MB free
- **After displaying bitmap:** ~1.8+ MB free
- **Stable across many consecutive requests**

### Building Compiled Modules

The deployment script automatically compiles Python modules to `.mpy` bytecode:

```bash
npm run deploy
```

This uses `mpy-cross` via WSL to compile all modules except:
- `code.py` (must remain as `.py` - entry point)
- `boot.py` (must remain as `.py` - boot configuration)
- `settings.toml.example` (template file)

**Benefits:**
- 37% smaller file size
- 9-14 KB less RAM usage
- Eliminates compilation-time memory fragmentation
- Faster module loading

## Troubleshooting

### Device won't connect to WiFi
- Check `settings.toml` credentials are correct
- Verify `settings.toml` is on the CIRCUITPY drive (not in git repo)
- Check serial console for connection error messages
- Try both 2.4GHz and 5GHz networks (S3 supports both)

### `EADDRINUSE` error (port 80 in use)
This means CircuitPython's built-in web workflow is using port 80.

**Solution:** Disable web workflow in `settings.toml`:
```toml
CIRCUITPY_WEB_API_PASSWORD = ""
```

**Why this happens:**
- The S3 has built-in WiFi, so CircuitPython enables web workflow by default
- Web workflow provides WiFi access to the CIRCUITPY drive on port 80
- Our HTTP server also needs port 80
- Setting an empty password disables web workflow

**Alternative:** Change your server to use port 8080 (modify line 78 in `code.py`)

### Memory allocation errors
- Ensure only one bitmap is in RAM at a time
- Check bitmap file size (should be ~6KB for 64x32x24bit)
- Monitor serial console for memory free reports
- Verify `.mpy` modules are deployed (run `npm run deploy`)

### Bitmap doesn't display
- Verify bitmap is exactly 64x32 pixels
- Check bitmap is 24-bit RGB format (not indexed color)
- Monitor serial console for parsing errors
- Try the `/clear` endpoint first to ensure display is working

### Crash logs not persisting
- Check if pin A1 is grounded (enables filesystem write mode)
- See `boot.py` for filesystem write mode configuration
- Logs are buffered in memory if filesystem is read-only
- View logs via `/crash` endpoint even if filesystem is read-only

## Migrating from MatrixPortal M4

If you're upgrading from the M4 version:

1. **No custom firmware needed** - Use standard CircuitPython for S3
2. **Replace `secrets.py` with `settings.toml`** - See setup instructions above
3. **Disable web workflow** - Add `CIRCUITPY_WEB_API_PASSWORD = ""` to settings
4. **Enjoy better performance** - Hardware parallel matrix control is faster
5. **More memory available** - 2MB PSRAM vs 192KB RAM

All API endpoints and bitmap formats remain the same - clients don't need updates.

## Contributing

This is an embedded device project optimized for memory efficiency. When contributing:

1. **Test memory usage** - Monitor `gc.mem_free()` before/after changes
2. **Pre-allocate buffers** - Avoid multiple small allocations
3. **Clean up immediately** - Delete temporary objects and call `gc.collect()`
4. **Test multiple requests** - Ensure no memory leaks across 6+ requests
5. **Use `.mpy` compilation** - Keep modules compilable with mpy-cross

## License

SPDX-License-Identifier: MIT
