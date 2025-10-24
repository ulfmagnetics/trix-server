"""
MatrixPortal M4 - Hello World Example
This is a simple proof of concept that prints to the serial console.
"""

import time
import board
import digitalio

# Set up the onboard LED
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

print("MatrixPortal Hello World!")
print("Starting main loop...")

# Simple blink loop
counter = 0
while True:
    led.value = True
    print(f"Hello from MatrixPortal! Count: {counter}")
    time.sleep(0.5)

    led.value = False
    time.sleep(0.5)

    counter += 1
