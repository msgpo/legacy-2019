import sys
import time
from collections import defaultdict

# Simple demo of of the WS2801/SPI-like addressable RGB LED lights.
import RPi.GPIO as GPIO

# Import the WS2801 module.
import Adafruit_WS2801
import Adafruit_GPIO.SPI as SPI

# Library to get RGB values from color name
import webcolors

# Matrix math
import numpy as np

# Image library
from PIL import Image

# Configure the count of pixels:
PIXEL_COUNT = 32

# Alternatively specify a hardware SPI connection on /dev/spidev0.0:
SPI_PORT = 0
SPI_DEVICE = 0
pixels = Adafruit_WS2801.WS2801Pixels(
    PIXEL_COUNT, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE), gpio=GPIO
)

# ----------------------------------------------------------------------------

def make_wheel():
    wheel = np.zeros(shape=(256, 3), dtype=np.uint8)

    for i in range(256):
        pos = i
        if pos < 85:
            pos = (pos * 3) % 256
            wheel[i, :] = [0, 255 - pos, pos]
        elif pos < 170:
            pos = ((pos - 85) * 3) % 256
            wheel[i, :] = [pos, 0, 255 - pos]
        else:
            pos = ((pos - 170) * 3) % 256
            wheel[i, :] = [255 - pos, 0, pos]

    return wheel

wheel = make_wheel()

def rainbow():
    return wheel[np.linspace(0, 255, PIXEL_COUNT, dtype=int),:]

# ----------------------------------------------------------------------------

PATTERNS = {
    "rainbow": rainbow
}

COMMANDS = defaultdict(list)

# ----------------------------------------------------------------------------

current_command = None
sample = False

def handle_command(command):
    global current_command, sample
    if command.endswith(".") and (command[:-1] == current_command):
        current_command = None
        return

    if current_command is not None:
        COMMANDS[current_command].append(command)
        return

    try:
        seconds = float(command)
        time.sleep(seconds)
        return
    except ValueError:
        pass  # not a decimal

    # Image sample
    if sample:
        sample = False
        sample_path = command
        sample_img = Image.open(sample_path)
        for x in range(sample_img.width):
            for y in range(sample_img.height):
                r, g, b = sample_img.getpixel((x, y))
                pixels.set_pixel_rgb(y, b, g, r)
            pixels.show()
            time.sleep(0.05)
        return

    command = command.lower()
    if command.endswith(":"):
        current_command = command[:-1]
        return
    elif "*" in command:
        count, command_name = command.split("*", maxsplit=1)
        count = int(count)
        for i in range(count):
            handle_command(command_name)
    elif command == "sample":
        sample = True
    elif command in COMMANDS:
        for command_name in COMMANDS[command]:
            handle_command(command_name)
    elif command in PATTERNS:
        for i, (r, g, b) in enumerate(PATTERNS[command]()):
            pixels.set_pixel_rgb(i, int(b), int(g), int(r))
    else:
        r, g, b = webcolors.name_to_rgb(command)
        for i in range(PIXEL_COUNT):
            pixels.set_pixel_rgb(i, b, g, r)

    pixels.show()

# ----------------------------------------------------------------------------

if __name__ == "__main__":
    commands = ["white"]
    if len(sys.argv) > 1:
        commands = sys.argv[1:]

    pixels.clear()

    for command in commands:
        handle_command(command)
