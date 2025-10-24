# trix-server

MatrixPortal M4 development and deployment system using CircuitPython.

## Project Structure

- `matrixportal/` - CircuitPython source code for the MatrixPortal M4
  - `code.py` - Main entry point (auto-runs on device boot)
- `scripts/` - Node.js deployment scripts
  - `deploy.js` - Deployment script
- `deploy-config.json` - Deployment configuration (target drive letter)

## Getting Started

### Prerequisites

- Adafruit MatrixPortal M4 with CircuitPython installed
- Node.js installed on your development machine

### Development Workflow

1. **Edit your code** in the `matrixportal/` directory
   - The main file is `code.py` which runs automatically when the MatrixPortal boots

2. **Connect your MatrixPortal** via USB
   - It should mount as a drive (default: E:)
   - If it mounts to a different drive letter, update `deploy-config.json`

3. **Deploy to your device** by running:
   ```bash
   npm run deploy
   ```
   - This copies all files from `matrixportal/` to your MatrixPortal
   - The device will automatically reset and run the new code

### Configuration

Edit `deploy-config.json` to change deployment settings:

```json
{
  "targetDrive": "E:",
  "sourceDir": "matrixportal"
}
```

## Hello World Example

The included `code.py` is a simple proof of concept that:
- Blinks the onboard LED
- Prints messages to the serial console
- Demonstrates the basic structure of a CircuitPython program

To view serial output, use a serial monitor like:
- Arduino Serial Monitor
- PuTTY
- Screen (on Mac/Linux)
- Mu Editor (recommended for CircuitPython development)