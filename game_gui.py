#!/usr/bin/env python3
import os
import sys
import time
import queue
from queue import Queue
import argparse
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
from tkinter import ttk
import logging
import itertools
import collections

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARN)
logging.getLogger("colormath.color_conversions").setLevel(logging.WARN)

import numpy as np
import pygame
import requests
from PIL import Image

from colormath.color_conversions import convert_color
from colormath.color_objects import sRGBColor, XYZColor, HSLColor, CMYColor

# Number of pixels in the LED strip
PIXEL_COUNT = 32

# -----------------------------------------------------------------------------

parser = argparse.ArgumentParser("game_gui.py")
parser.add_argument("--no-pi", action="store_true", help="Disable LED strip on pi")

args = parser.parse_args()
logging.debug(args)

# -----------------------------------------------------------------------------

# Index to button name
BUTTONS = {
    0: "a",
    1: "b",
    2: "x",
    3: "y",
    4: "lb",
    5: "rb",
    6: "back",
    7: "start",
    8: "logitech",
    9: "lstick",
    10: "rstick",
}

# Index to "hat" (d-pad) name
HATS = {(0, 1): "up", (0, -1): "down", (-1, 0): "left", (1, 0): "right"}

# Index to axis name
AXES = {0: "lx", 1: "ly", 3: "rx", 4: "ry"}

# Index to trigger name
TRIGGERS = {2: "lt", 5: "rt"}

# Name to TK combo box
COMBOS = {
    "back": {"x": 460, "y": 240},
    "start": {"x": 665, "y": 240},
    "lb": {"x": 270, "y": 100},
    "rb": {"x": 865, "y": 100},
    "lt": {"x": 270, "y": 55},
    "rt": {"x": 865, "y": 55},
    "y": {"x": 850, "y": 225},
    "b": {"x": 1005, "y": 360},
    "a": {"x": 930, "y": 438},
    "x": {"x": 685, "y": 365},
    "lstick": {"x": 419, "y": 526},
    "rstick": {"x": 708, "y": 526},
    "lx": {"x": 305, "y": 526},
    "ly": {"x": 419, "y": 625},
    "rx": {"x": 830, "y": 526},
    "ry": {"x": 830, "y": 625},
    "up": {"x": 275, "y": 250},
    "down": {"x": 275, "y": 470},
    "left": {"x": 150, "y": 360},
    "right": {"x": 400, "y": 360},
    "logitech": {"x": 565, "y": 325},
}

# Operations that are on/off
DISCRETE_OPS = [
    "-",
    "Red",
    "Orange",
    "Yellow",
    "Green",
    "Blue",
    "Indigo",
    "Violet",
    "Pink",
    "Bright",
    "Dark",
    "White",
    "Black",
    "Copy",
    "One",
    "Evens",
    "Odds",
    "Rainbow",
    "Alt",
    "Gradient",
    "Record",
]

# Operations that vary
CONT_OPS = ["-", "Red", "Green", "Blue", "Hue", "Light", "Roll", "RollL", "RollR"]

# Button/hat assignments by name
BUTTON_OPS = {
    "a": "Green",
    "b": "Red",
    "x": "Blue",
    "y": "Orange",
    "lstick": "Bright",
    "rstick": "Dark",
    "lb": "Alt",
    "rb": "Copy",
    "start": "Gradient",
    "logitech": "Record",
    "back": "Black",
    "up": "One",
    "down": "Rainbow",
    "left": "Evens",
    "right": "Odds",
}

# Axis assignments by name
AXIS_OPS = {"lx": "Light", "ly": "Hue", "rx": "Red", "ry": "Blue"}

# Trigger assignments by name
TRIGGER_OPS = {"lt": "RollL", "rt": "RollR"}

# Delay between animation frames
ANIMATION_DELAY = 0.05

# Function called every frame to transform pixels
ANIMATION_STEP = lambda x: x

# -------------------------------------------------------------------------

# True if colors are being recorded to an image
recording = False
playing = False
record_buffer = []


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()

        self.queue = Queue()
        self.master.after(100, self.process_queue)

    def create_widgets(self):
        self.menubar = tk.Menu(self.master, tearoff=0)
        self.menubar_bg = self.menubar["background"]

        file_menu = tk.Menu(self.menubar)
        file_menu.add_command(label="Open", command=self.file_open)
        file_menu.add_command(label="Save", command=self.file_save)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)

        self.menubar.add_cascade(label="File", menu=file_menu)
        self.master.config(menu=self.menubar)

        self.bg_image = tk.PhotoImage(file="img/controller.png")
        self.bg_label = tk.Label(self, image=self.bg_image)
        self.bg_label.pack()

        style = ttk.Style()
        style.map("TCombobox", fieldbackground=[("readonly", "white")])
        style.map("TCombobox", selectbackground=[("readonly", "white")])
        style.map("TCombobox", selectforeground=[("readonly", "black")])

        # Highlight when button/axis used
        style.configure("Red.TCombobox", foreground="red", background="red")

        self.combos = {
            name: self._make_combo(name, **kwargs) for name, kwargs in COMBOS.items()
        }

        for name, combo in list(self.combos.items()):
            self.combos[repr(combo)] = name

    # -------------------------------------------------------------------------

    def file_open(self):
        global playing, record_buffer
        try:
            file_name = filedialog.askopenfilename(
                parent=self,
                initialdir=os.getcwd(),
                title="Select an image",
                filetypes=(("Image Files", "*.png *.jpg *.jpeg"), ("All Files", "*.*")),
            )

            if file_name:
                logging.debug("Loading %s" % file_name)
                record_img = Image.open(file_name)
                record_buffer = list(
                    reversed((np.swapaxes(np.array(record_img), 0, 1)).tolist())
                )
                logging.info("Playing back %s frame(s)" % len(record_buffer))
                recording = False
                playing = True
        except Exception as e:
            logging.exception("file_save")

    def file_save(self):
        global record_buffer
        try:
            file_name = filedialog.asksaveasfilename(
                parent=self,
                initialdir=os.getcwd(),
                title="Save image",
                filetypes=(("Image Files", "*.png"), ("All Files", "*.*")),
            )

            if file_name:
                logging.debug("Saving %s" % file_name)
                record_array = np.hstack(record_buffer).reshape(
                    (PIXEL_COUNT, len(record_buffer), 3)
                )
                Image.fromarray(record_array, mode="RGB").save(file_name)
        except Exception as e:
            logging.exception("file_save")

    # -------------------------------------------------------------------------

    def _make_combo(self, name, x, y):
        values = DISCRETE_OPS
        if (name in AXES.values()) or (name in TRIGGERS.values()):
            values = CONT_OPS

        combo = ttk.Combobox(self, values=values, state="readonly")
        combo.bind("<<ComboboxSelected>>", self._handle_selected)
        combo.current(0)

        if name in BUTTON_OPS:
            combo.current(DISCRETE_OPS.index(BUTTON_OPS[name]))
        elif name in AXIS_OPS:
            combo.current(CONT_OPS.index(AXIS_OPS[name]))
        elif name in TRIGGER_OPS:
            combo.current(CONT_OPS.index(TRIGGER_OPS[name]))

        self._set_op(name, combo.current())
        combo.place(x=x, y=y, width=75, anchor=tk.CENTER)
        return combo

    def _handle_selected(self, event):
        try:
            name = self.combos[repr(event.widget)]
            index = event.widget.current()
            self._set_op(name, index)
        except Exception as e:
            logging.exception("handle_selected")

    def _set_op(self, name, index):
        try:
            if (name in BUTTONS.values()) or (name in HATS.values()):
                BUTTON_OPS[name] = DISCRETE_OPS[index]
            else:
                AXIS_OPS[name] = CONT_OPS[index]
        except Exception as e:
            logging.exception("set_op")

    # -------------------------------------------------------------------------

    def process_queue(self):
        """Process incoming events from Pygame thread"""
        global recording, playing
        try:
            while True:
                # Show recording status
                if recording:
                    self.master.title("LEGACY (Recording)")
                    self.menubar["background"] = "red"
                elif playing:
                    self.master.title("LEGACY (Playing)")
                    self.menubar["background"] = "green"
                else:
                    self.master.title("LEGACY")
                    self.menubar["background"] = self.menubar_bg

                # Throws queue.Empty when empty
                event = self.queue.get_nowait()

                # Process event
                if event.type in [pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP]:
                    # Button up/down
                    combo_name = BUTTONS.get(event.button, None)
                    if combo_name:
                        # Highlight combo box
                        combo = self.combos[combo_name]
                        if event.type == pygame.JOYBUTTONDOWN:
                            combo["style"] = "Red.TCombobox"
                        elif event.type == pygame.JOYBUTTONUP:
                            combo["style"] = "TCombobox"
                elif event.type == pygame.JOYAXISMOTION:
                    # Stick movement
                    combo_name = AXES.get(event.axis, None)
                    if combo_name:
                        # Highlight combo box
                        combo = self.combos[combo_name]
                        if (event.value < -0.1) or (event.value > 0.1):
                            combo["style"] = "Red.TCombobox"
                        else:
                            combo["style"] = "TCombobox"
                    else:
                        # Highlight combo box
                        combo_name = TRIGGERS.get(event.axis, None)
                        if combo_name:
                            combo = self.combos[combo_name]
                            if event.value > -0.9:
                                combo["style"] = "Red.TCombobox"
                            else:
                                combo["style"] = "TCombobox"
                elif event.type == pygame.JOYHATMOTION:
                    # Hat (d-pad) up/down
                    if event.value == (0, 0):
                        # No buttons pressed
                        for name in ["up", "down", "left", "right"]:
                            self.combos[name]["style"] = "TCombobox"
                    else:
                        # Vertical
                        if event.value == (0, 1):
                            self.combos["up"]["style"] = "Red.TCombobox"
                        elif event.value == (0, -1):
                            self.combos["down"]["style"] = "Red.TCombobox"

                        # Horizontal
                        if event.value == (1, 0):
                            self.combos["right"]["style"] = "Red.TCombobox"
                        elif event.value == (-1, 0):
                            self.combos["left"]["style"] = "Red.TCombobox"
        except queue.Empty:
            pass
        except Exception as e:
            logging.exception("process_queue")
        finally:
            self.master.after(100, self.process_queue)


# -----------------------------------------------------------------------------


def pygame_run(app):
    """Thread to watch for Pygame events, handle them, and forward to TK app."""

    # Initialize Pygame
    pygame.init()
    pygame.mixer.quit()

    pygame.joystick.init()
    joysticks = [
        pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())
    ]

    assert len(joysticks) > 0, "No game controller"

    # Default to first joystick (gamepad)
    js = joysticks[0]
    js.init()

    while True:
        try:
            # Wait here until first event arruves
            events = [pygame.event.wait()]
            for event in events + pygame.event.get():
                # Check if this is an event we care about
                if event.type in [
                    pygame.JOYBUTTONUP,
                    pygame.JOYBUTTONDOWN,
                    pygame.JOYAXISMOTION,
                    pygame.JOYHATMOTION,
                ]:
                    # Forward to TK app
                    app.queue.put(event)
                    # logging.debug(event)

                    if event.type in [pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP]:
                        # Button up/down
                        button_name = BUTTONS.get(event.button, "")
                        op = BUTTON_OPS.get(button_name, None)
                        if op:
                            on = event.type == pygame.JOYBUTTONDOWN
                            do_discrete_op(button_name, op, on=on)
                    elif event.type == pygame.JOYHATMOTION:
                        # HAT (d-pad) button
                        if event.value == (0, 0):
                            # No buttons pressed
                            for hat_name in HATS.values():
                                op = BUTTON_OPS.get(hat_name, None)
                                if op:
                                    do_discrete_op(hat_name, op, on=False)
                        else:
                            # Button pressed
                            hat_name = HATS.get(event.value, "")
                            op = BUTTON_OPS.get(hat_name, None)
                            if op:
                                do_discrete_op(hat_name, op, on=True)
                    if event.type == pygame.JOYAXISMOTION:
                        # Stick motion
                        if event.axis in TRIGGERS:
                            axis_name = TRIGGERS.get(event.axis, "")
                            value = (event.value + 1) / 2
                        else:
                            axis_name = AXES.get(event.axis, "")
                            value = event.value

                        op = AXIS_OPS.get(axis_name, None)
                        if op:
                            do_cont_op(axis_name, op, value)
        except Exception as e:
            logging.exception("pygame_run")


# -----------------------------------------------------------------------------

base_pixels = np.zeros(shape=(PIXEL_COUNT, 3), dtype=np.uint8)
shown_pixels = np.zeros(shape=(PIXEL_COUNT, 3), dtype=np.uint8)


def animation_run():
    global base_pixels, shown_pixels, ANIMATION_STEP, ANIMATION_DELAY, playing

    while True:
        try:
            if playing:
                if len(record_buffer) > 0:
                    after_pixels = np.array(record_buffer.pop(), dtype=np.uint8)
                else:
                    logging.info("Finished playback")
                    playing = False

            if not playing:
                base_pixels = ANIMATION_STEP(base_pixels)
                after_pixels = apply_ops(base_pixels)

            if not np.array_equal(after_pixels, shown_pixels):
                shown_pixels = after_pixels
                update_pixels(shown_pixels)

            if recording:
                record_buffer.append(shown_pixels)
        except Exception as e:
            logging.exception("animation_run")

        time.sleep(ANIMATION_DELAY)


# -----------------------------------------------------------------------------


colorspace_map = {"rgb": sRGBColor, "hsl": HSLColor, "cmy": CMYColor}
sums = {
    op_name: {
        ctrl_name: np.zeros(shape=(PIXEL_COUNT, 3), dtype=int)
        for ctrl_name in itertools.chain(
            BUTTONS.values(), AXES.values(), TRIGGERS.values(), HATS.values()
        )
    }
    for op_name in DISCRETE_OPS + CONT_OPS
}

stages = {
    "rgb": [
        "Red",
        "Green",
        "Blue",
        "Yellow",
        "Orange",
        "Indigo",
        "Violet",
        "Pink",
        "White",
        "Black",
        "Rainbow",
        "One",
        "Evens",
        "Odds",
    ],
    "hsl": ["Bright", "Dark", "Hue", "Light"],
}


def wheel(pos):
    """Returns colors across a color wheel"""
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)


# True if alterantive operation is enabled
alt = False

# True if colors should be in a gradient instead of solid
gradient = False


def color_sum(op, ctrl_name, dim, on, value=255, alt_value=None):
    """Fills pixel array for a solid color. Handles alt/gradient variations."""
    global alt, gradient
    if alt_value is None:
        alt_value = -value

    if gradient:
        if not isinstance(dim, collections.Iterable):
            dim = [dim]

        # Fill color dimensions independently
        for d in dim:
            sums[op][ctrl_name][:, d] = (
                np.linspace(0, value + 1, PIXEL_COUNT) if on else 0
            )
    else:
        sums[op][ctrl_name][:, dim] = (alt_value if alt else value) if on else 0


def do_discrete_op(ctrl_name, op, on=True):
    """Perform discrete color transformations."""
    global base_pixels, shown_pixels, alt, gradient, ANIMATION_STEP, ANIMATION_DELAY, recording

    if op == "Alt":
        # Do alternatve operation
        alt = on
    elif op == "Gradient":
        # Do color gradients
        gradient = on
    elif op == "Red":
        color_sum(op, ctrl_name, 0, on)
    elif op == "Green":
        color_sum(op, ctrl_name, 1, on)
    elif op == "Blue":
        color_sum(op, ctrl_name, 2, on)
    elif op == "Yellow":
        color_sum(op, ctrl_name, [0, 1], on)
    elif op == "Orange":
        color_sum(op, ctrl_name, 0, on)
        color_sum(op, ctrl_name, 1, on, 128)
    elif op == "Indigo":
        color_sum(op, ctrl_name, [1, 2], on)
    elif op == "Violet":
        color_sum(op, ctrl_name, [0, 2], on)
    elif op == "Violet":
        color_sum(op, ctrl_name, 0, on)
        color_sum(op, ctrl_name, 2, on, 128)
    elif op == "Bright":
        color_sum(op, ctrl_name, 2, on, 50, 100)
    elif op == "Dark":
        color_sum(op, ctrl_name, 2, on, -50, -100)
    elif op == "White":
        color_sum(op, ctrl_name, [0, 1, 2], on, 255)
    elif op == "Black":
        color_sum(op, ctrl_name, [0, 1, 2], on, -255)
    elif op == "Rainbow":
        rainbow_array = sums[op][ctrl_name]
        for i in range(PIXEL_COUNT):
            rainbow_array[i, :] = wheel(int(i * (256 / PIXEL_COUNT))) if on else 0
            if alt:
                rainbow_array[i, :] = np.roll(rainbow_array[i, :], shift=2)
    elif op == "One":
        sums[op][ctrl_name][:, :] = -255 if on else 0
        sums[op][ctrl_name][0, :] = 0
    elif op == "Odds":
        sums[op][ctrl_name][:, :] = -255 if on else 0
        sums[op][ctrl_name][::2, :] = 0
    elif op == "Evens":
        sums[op][ctrl_name][:, :] = 0
        sums[op][ctrl_name][::2, :] = -255 if on else 0
    elif op == "Copy" and on:
        base_pixels = np.array(shown_pixels)

        # Reset all sums
        for ctrl_arrays in sums.values():
            for ctrl_array in ctrl_arrays.values():
                ctrl_array[:, :] = 0
    elif op == "Record" and on:
        recording = not recording
        if recording:
            playing = False
            record_buffer = []
            logging.info("Started recording")
        else:
            logging.info("Stopped recording")


def do_cont_op(ctrl_name, op, value):
    """Perform continuous color transformations."""
    global ANIMATION_STEP, ANIMATION_DELAY

    if op == "Light":
        sums[op][ctrl_name][:, 2] = 255 * value
    elif op == "Hue":
        sums[op][ctrl_name][:, 0] = 255 * value
    elif op == "Red":
        sums[op][ctrl_name][:, 0] = 255 * value
    elif op == "Green":
        sums[op][ctrl_name][:, 1] = 255 * value
    elif op == "Blue":
        sums[op][ctrl_name][:, 2] = 255 * value
    elif op == "Roll":
        if (value < -0.05) or (value > 0.05):
            roll = -1 if value < 0 else 1
            ANIMATION_STEP = lambda x: np.roll(x, roll, axis=0)
            ANIMATION_DELAY = 0.01 + ((0.1 - 0.01) * (1 - np.abs(value)))
        else:
            ANIMATION_STEP = lambda x: x
            ANIMATION_DELAY = 0.05
    elif op == "RollL":
        if value > 0.05:
            ANIMATION_STEP = lambda x: np.roll(x, -1, axis=0)
            ANIMATION_DELAY = 0.01 + ((0.1 - 0.01) * (1 - value))
        else:
            ANIMATION_STEP = lambda x: x
            ANIMATION_DELAY = 0.05
    elif op == "RollR":
        if value > 0.05:
            ANIMATION_STEP = lambda x: np.roll(x, 1, axis=0)
            ANIMATION_DELAY = 0.01 + ((0.1 - 0.01) * (1 - value))
        else:
            ANIMATION_STEP = lambda x: x
            ANIMATION_DELAY = 0.05


# -----------------------------------------------------------------------------


def apply_ops(pixels):
    current_rgb = np.array(pixels, dtype=int)

    # Do RGB operations
    for op in stages["rgb"]:
        if op in sums:
            for ctrl_array in sums[op].values():
                current_rgb += ctrl_array

    try:
        # Do HSL operations
        np.clip(current_rgb, 0, 255, out=current_rgb)
        current_hsl = np.zeros_like(current_rgb)
        for i in range(PIXEL_COUNT):
            current_hsl[i, :] = convert_color(
                sRGBColor(*current_rgb[i]), HSLColor
            ).get_value_tuple()

        for op in stages["hsl"]:
            if op in sums:
                for ctrl_array in sums[op].values():
                    current_hsl += ctrl_array

        # Convert to RGB finally
        final_rgb = np.zeros_like(current_hsl)
        for i in range(PIXEL_COUNT):
            final_rgb[i, :] = convert_color(
                HSLColor(*current_hsl[i]), sRGBColor
            ).get_value_tuple()
    except Exception as e:
        logging.exception("update_pixels")
        final_rgb = current_rgb

    # Final clipping
    np.clip(final_rgb, 0, 255, out=final_rgb)

    return final_rgb.astype(np.uint8)


if args.no_pi:
    # Use web server
    def update_pixels(pixels):
        pixels_json = [
            [int(pixels[i, 0]), int(pixels[i, 1]), int(pixels[i, 2])]
            for i in range(PIXEL_COUNT)
        ]

        requests.post("http://localhost:5000/pixels/rgb", json=pixels_json)


else:
    import RPi.GPIO as GPIO
    import Adafruit_WS2801 as WS2801
    import Adafruit_GPIO.SPI as SPI

    # Hardware address of LED strip (must enable SPI in raspi-config)
    real_pixels = WS2801.WS2801Pixels(PIXEL_COUNT, spi=SPI.SpiDev(0, 0), gpio=GPIO)

    # Use actual LED strip
    def update_pixels(pixels):
        global real_pixels
        for i in range(PIXEL_COUNT):
            real_pixels.set_pixel_rgb(
                i, int(pixels[i, 2]), int(pixels[i, 1]), int(pixels[i, 0])
            )

        real_pixels.show()


# -----------------------------------------------------------------------------


def main():
    root = tk.Tk()
    app = Application(master=root)
    app.master.title("LEGACY")

    # Animation thread
    threading.Thread(target=animation_run, daemon=True).start()

    # Pygame thread
    threading.Thread(target=pygame_run, args=[app], daemon=True).start()

    root.mainloop()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
