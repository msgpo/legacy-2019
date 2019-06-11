#!/usr/bin/env python3
import os
import time
import json
import signal
import argparse
import shlex
import logging
import time
from uuid import uuid4

logging.basicConfig(level=logging.DEBUG)

import numpy as np
import gevent
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_sockets import Sockets
from colormath.color_objects import (
    LabColor,
    sRGBColor,
    LuvColor,
    XYZColor,
    HSLColor,
    HSVColor,
    CMYColor,
    IPTColor,
)

logging.getLogger("colormath.color_conversions").setLevel(logging.WARN)
from colormath.color_conversions import convert_color

import webcolors

# -----------------------------------------------------------------------------

parser = argparse.ArgumentParser("server.py")
parser.add_argument("--no-pi", action="store_true", help="Disable LED strip on pi")
parser.add_argument("--host", default="127.0.0.1", help="Host for server")
parser.add_argument("--port", default=5000, type=int, help="Port for server")

args = parser.parse_args()
logging.debug(args)

# -----------------------------------------------------------------------------

# Number of LEDs on the strip
PIXEL_COUNT = 32

if args.no_pi:

    class FakePixels:
        def __init__(self, pixel_count=PIXEL_COUNT):
            self.pixel_count = pixel_count
            self.rgb = np.zeros(shape=(self.pixel_count, 3), dtype=np.uint8)
            self.rgb_show = np.zeros(shape=(self.pixel_count, 3), dtype=np.uint8)
            self.source_color = sRGBColor

        def clear(self):
            self.rgb[:, :] = 0

        def show(self):
            for i in range(self.pixel_count):
                r, g, b, = self.rgb[i, :]

                # Convert color
                target_color = convert_color(
                    self.source_color(r / 255, g / 255, b / 255), sRGBColor
                )
                r, g, b, = (
                    max(min(int(v * 255), 255), 0)
                    for v in target_color.get_value_tuple()
                )

                self.rgb_show[i, :] = (r, g, b)

        def set_pixel_rgb(self, i, b, g, r):
            i = i % self.pixel_count
            self.rgb[i, 0] = r
            self.rgb[i, 1] = g
            self.rgb[i, 2] = b

        def get_pixel_rgb(self, i):
            i = i % self.pixel_count
            r, g, b = self.rgb_show[i, :]
            return b, g, r

    pixels = FakePixels(PIXEL_COUNT)
else:
    import RPi.GPIO as GPIO
    import Adafruit_WS2801 as WS2801
    import Adafruit_GPIO.SPI as SPI

    # Hardware address of LED strip (must enable SPI in raspi-config)
    class RealPixels:
        def __init__(self, pixel_count=PIXEL_COUNT, spi_port=0, spi_device=0):
            self.pixel_count = pixel_count
            self.rgb = np.zeros(shape=(self.pixel_count, 3), dtype=np.uint8)
            self.source_color = sRGBColor
            self.real_pixels = WS2801.WS2801Pixels(
                self.pixel_count, spi=SPI.SpiDev(spi_port, spi_device), gpio=GPIO
            )

        def clear(self):
            for i in range(self.pixel_count):
                self.set_pixel_rgb(i, 0, 0, 0)

        def show(self):
            for i in range(self.pixel_count):
                self.set_pixel_rgb(
                    i, int(self.rgb[i, 2]), int(self.rgb[i, 1]), int(self.rgb[i, 0])
                )

            self.real_pixels.show()

        def set_pixel_rgb(self, i, b, g, r):
            i = i % self.pixel_count
            self.rgb[i, 0] = r
            self.rgb[i, 1] = g
            self.rgb[i, 2] = b

            # Convert color
            target_color = convert_color(
                self.source_color(r / 255, g / 255, b / 255), sRGBColor
            )
            r, g, b, = (
                max(min(int(v * 255), 255), 0) for v in target_color.get_value_tuple()
            )
            self.real_pixels.set_pixel_rgb(i, b, g, r)

        def get_pixel_rgb(self, i):
            return self.real_pixels.get_pixel_rgb(i)

    pixels = RealPixels(PIXEL_COUNT)

# Turn off the LED strip
pixels.clear()
pixels.show()

# -----------------------------------------------------------------------------

# Web server
app = Flask("legacy-2019")
app.secret_key = str(uuid4())
sockets = Sockets(app)

show_event = gevent.event.Event()


def show_pixels():
    pixels.show()
    show_event.set()
    show_event.clear()


# -----------------------------------------------------------------------------

# Examples:
# GET /pixel/0 -> { "i": 0, "r": 255, "g": 0, "b": 255 }
# GET /pixel/0/r -> 255
# GET /pixel/0/rb -> [255, 255]
# POST /pixel/0 with { "i": 0, "r": 255, "g": 0, "b": 255 } -> pixel 0 is red
# POST /pixel/0/r with 255 -> pixel 0 is red
# POST /pixel/0/rb with 255 -> pixel 0 is purple
@app.route("/pixel/<int:index>", methods=["GET", "POST"])
@app.route("/pixel/<int:index>/<channel>", methods=["GET", "POST"])
def api_pixel(index, channel=None):
    # Ensure index is in 0-31
    index = index % PIXEL_COUNT

    if channel:
        channel = channel.lower().strip()

    if request.method == "POST":
        # Ensure colors in 0-255
        if channel:
            try:
                value = int(request.data.decode()) % 256
            except:
                value = 0

            b, g, r = pixels.get_pixel_rgb(index)

            if channel == "off":
                # off
                r, g, b = 0, 0, 0
            elif channel == "on":
                # off
                r, g, b = 255, 255, 255
            else:
                # Set r, g, b
                if "r" in channel:
                    r = value

                if "g" in channel:
                    g = value

                if "b" in channel:
                    b = value
        else:
            value = json.loads(request.data.decode())
            if isinstance(value, dict):
                # Set r/g/b of pixel via JSON object
                r, g, b, = value.get("r", 0), value.get("g", 0), value.get("b", 0)
            else:
                # Set r/g/b of pixel via JSON list
                r, g, b = value

        pixels.set_pixel_rgb(index, b, g, r)
        show_pixels()

        return "OK"
    else:
        b, g, r = pixels.get_pixel_rgb(index)

        if channel:
            values = []
            if "r" in channel:
                values.append(r)
            if "g" in channel:
                values.append(g)
            if "b" in channel:
                values.append(b)

            if len(values) == 1:
                return str(values[0])
            else:
                return jsonify(values)
        else:
            # Get r/g/b of pixel
            return jsonify({"i": index, "r": r, "g": g, "b": b})


# -----------------------------------------------------------------------------


# Examples:
# GET /pixels/0 -> [{ "i": 0, "r": 255, "g": 0, "b": 0 }, { "i": 1, "r": 255, "g": 0, "b": 0 }, ...]
# GET /pixels/0/r -> [255, 0, 0, 0, ...]
# GET /pixels/0/rb -> [[255, 0], [0, 0], [0, 0], ...]
# POST /pixels with [{ "r": 255, "g": 0, "b": 0 }, ...] -> pixel 0 is red
# POST /pixels/r with [255, 0, 0, ...] -> pixel 0 is red
# POST /pixels/r with 255 -> all pixels are red
# POST /pixels/rb with 255 -> all pixels are purple
@app.route("/pixels", methods=["GET", "POST"])
@app.route("/pixels/<channel>", methods=["GET", "POST"])
def api_pixels(channel=None):
    if channel:
        channel = channel.lower().strip()

    if request.method == "POST":
        data = json.loads(request.data.decode())
        if not isinstance(data, list):
            data = [int(data)] * PIXEL_COUNT

        if channel == "raw":
            bgr = request.args.get("bgr", "false").lower().strip() == "true"
            for i in range(PIXEL_COUNT):
                i3 = i * 3
                if bgr:
                    b, g, r = data[i3 : i3 + 3]
                else:
                    r, g, b = data[i3 : i3 + 3]
                pixels.set_pixel_rgb(i, b, g, r)
        else:
            for i, value in enumerate(data):
                b, g, r = pixels.get_pixel_rgb(i)

                if channel:
                    if channel == "off":
                        # off
                        r, g, b = 0, 0, 0
                    elif channel == "on":
                        # off
                        r, g, b = 255, 255, 255
                    elif isinstance(value, list):
                        # Set r, g, b
                        r_idx = channel.find("r")
                        if r_idx >= 0:
                            r = value[r_idx]

                        g_idx = channel.find("g")
                        if g_idx >= 0:
                            g = value[g_idx]

                        b_idx = channel.find("b")
                        if b_idx >= 0:
                            b = value[b_idx]
                    else:
                        # Set r, g, b
                        if "r" in channel:
                            r = value

                        if "g" in channel:
                            g = value

                        if "b" in channel:
                            b = value
                elif isinstance(value, list):
                    r, g, b, = value
                else:
                    r, g, b, = value.get("r", 0), value.get("g", 0), value.get("b", 0)
                    i = value.get("i", i)

                pixels.set_pixel_rgb(i, b, g, r)

        show_pixels()
        return "OK"
    else:
        bgrs = [pixels.get_pixel_rgb(i) for i in range(PIXEL_COUNT)]

        if channel:
            values = []
            for bgr in bgrs:
                value = []
                if "r" in channel:
                    value.append(bgr[2])
                if "g" in channel:
                    value.append(bgr[1])
                if "b" in channel:
                    value.append(bgr[0])

                if len(value) == 1:
                    value = value[0]

                values.append(value)

            return jsonify(values)
        else:
            colors = [
                {
                    "i": i,
                    "r": int(bgrs[i][2]),
                    "g": int(bgrs[i][1]),
                    "b": int(bgrs[i][0]),
                }
                for i in range(PIXEL_COUNT)
            ]

            return jsonify(colors)


# -----------------------------------------------------------------------------


@app.route("/color/<color>", methods=["POST"])
@app.route("/color/<int:index>/<color>", methods=["POST"])
def api_color(color, index=None):
    steps = int(request.args.get("steps", 1))
    delay = float(request.args.get("delay", 0.05))

    color = color.lower().strip()
    final_rgb = np.array(webcolors.name_to_rgb(color), dtype=np.uint8)

    if index is None:
        # Set all
        start_rgb = np.array(pixels.rgb)
        step_rgb = (final_rgb - start_rgb) / steps

        for step in range(steps):
            pixels.rgb = start_rgb + (step * step_rgb)
            show_pixels()
            gevent.sleep(delay)

        pixels.rgb[:,] = final_rgb
        show_pixels()
    else:
        start_rgb = np.array(pixels.rgb[index, :])
        step_rgb = (final_rgb - start_rgb) / steps

        for step in range(steps):
            pixels.rgb[index, :] = start_rgb + (step * step_rgb)
            show_pixels()
            gevent.sleep(delay)

        pixels.rgb[index, :] = final_rgb
        show_pixels()

    return color


# -----------------------------------------------------------------------------


def wheel(pos):
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)


# -----------------------------------------------------------------------------


@app.route("/pattern", methods=["POST"])
@app.route("/pattern/<name>", methods=["POST"])
def pattern(name=None):
    if name is None:
        name = request.data.decode()

    name = name.lower().strip()
    if name == "rainbow":
        for i in range(PIXEL_COUNT):
            pixels.rgb[i, :] = wheel(int(i * (256 / PIXEL_COUNT)))
    elif name == "off":
        pixels.rgb[:, :] = 0

    show_pixels()

    return name


# -----------------------------------------------------------------------------


@app.route("/op", methods=["POST"])
@app.route("/op/<name>", methods=["POST"])
@app.route("/op/<name>/<int:count>", methods=["POST"])
@app.route("/op/<name>/<int:count>/<int:delay>", methods=["POST"])
def op(name=None, count=1, delay=250):
    if name is None:
        name = request.data.decode()

    name = name.lower().strip()
    op_func = None

    if name == "roll":
        try:
            amount = int(request.data.decode())
        except ValueError:
            amount = 1

        def roll():
            pixels.rgb[:, 0] = np.roll(pixels.rgb[:, 0], amount)
            pixels.rgb[:, 1] = np.roll(pixels.rgb[:, 1], amount)
            pixels.rgb[:, 2] = np.roll(pixels.rgb[:, 2], amount)

        op_func = roll

    if op_func:
        delay_sec = delay / 1000
        for i in range(count):
            op_func()
            show_pixels()
            gevent.sleep(delay_sec)

    return name


# -----------------------------------------------------------------------------

colorspace_map = {
    # "lab": LabColor,
    "rgb": sRGBColor,
    # "luv": LuvColor,
    "xyz": XYZColor,
    "hsl": HSLColor,
    # "hsv": HSVColor,
    "cmy": CMYColor,
    "ipt": IPTColor,
}


@app.route("/colorspace", methods=["POST", "GET"])
def colorspace():
    if request.method == "GET":
        return jsonify(colorspace_map.keys())

    name = request.data.decode().strip().lower()
    pixels.source_color = colorspace_map.get(name, sRGBColor)
    show_pixels()

    return "OK"


# -----------------------------------------------------------------------------


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/css/<path:filename>", methods=["GET"])
def css(filename):
    return send_from_directory(os.path.join(".", "css"), filename)


@app.route("/js/<path:filename>", methods=["GET"])
def js(filename):
    return send_from_directory(os.path.join(".", "js"), filename)


# -----------------------------------------------------------------------------


def send_pixels(ws):
    bgrs = [pixels.get_pixel_rgb(i) for i in range(PIXEL_COUNT)]
    colors = [
        {"i": i, "r": int(bgrs[i][2]), "g": int(bgrs[i][1]), "b": int(bgrs[i][0])}
        for i in range(PIXEL_COUNT)
    ]

    ws.send(json.dumps(colors))


@sockets.route("/pixels")
def pixels_ws(ws):
    send_pixels(ws)
    while not ws.closed:
        show_event.wait()
        send_pixels(ws)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    server = pywsgi.WSGIServer(
        (args.host, args.port), app, handler_class=WebSocketHandler
    )

    logging.getLogger("geventwebsocket").setLevel(logging.WARN)

    logging.info("Service at http://%s:%s" % (args.host, args.port))
    server.serve_forever()
