#!/usr/bin/env python3
import sys
import time
import queue
from queue import Queue
import threading
import tkinter as tk
from tkinter import ttk
import logging
import itertools

logging.basicConfig(level=logging.DEBUG)

import numpy as np
import pygame
import requests
from colormath.color_conversions import convert_color
from colormath.color_objects import sRGBColor, XYZColor, HSLColor, CMYColor

PIXEL_COUNT = 32

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
    "Bright",
    "Dark",
    "White",
    "Black",
    "Copy",
    "One",
    "Evens",
    "Odds",
    "Rainbow",
]

# Operations that vary
CONT_OPS = ["-", "Red", "Green", "Blue", "Hue", "Light", "Roll", "RollL", "RollR"]

# Button/hat assignments by name
BUTTON_OPS = {
    "a": "Green",
    "b": "Red",
    "x": "Blue",
    "y": "Yellow",
    "lstick": "Bright",
    "rstick": "Dark",
    "lb": "Orange",
    "rb": "Indigo",
    "start": "White",
    "logitech": "Copy",
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

ANIMATION_STEP = lambda x: x

# -------------------------------------------------------------------------


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()

        self.queue = Queue()
        self.master.after(100, self.process_queue)

    def create_widgets(self):
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
        try:
            while True:
                # Throws queue.Empty when empty
                event = self.queue.get_nowait()

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
    global base_pixels, shown_pixels, ANIMATION_STEP, ANIMATION_DELAY

    while True:
        try:
            base_pixels = ANIMATION_STEP(base_pixels)
            after_pixels = apply_ops(base_pixels)

            if not np.array_equal(after_pixels, shown_pixels):
                shown_pixels = after_pixels
                update_pixels(shown_pixels)
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
        "White",
        "Black",
        "Rainbow",
        "One",
        "Evens",
        "Odds"
    ],
    "hsl": ["Bright", "Dark", "Hue", "Light"],
}


def wheel(pos):
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)


def do_discrete_op(ctrl_name, op, on=True):
    global base_pixels, shown_pixels

    if op == "Red":
        sums[op][ctrl_name][:, 0] = 255 if on else 0
    elif op == "Green":
        sums[op][ctrl_name][:, 1] = 255 if on else 0
    elif op == "Blue":
        sums[op][ctrl_name][:, 2] = 255 if on else 0
    elif op == "Yellow":
        sums[op][ctrl_name][:, 0] = 255 if on else 0
        sums[op][ctrl_name][:, 1] = 255 if on else 0
    elif op == "Orange":
        sums[op][ctrl_name][:, 0] = 255 if on else 0
        sums[op][ctrl_name][:, 1] = 128 if on else 0
    elif op == "Indigo":
        sums[op][ctrl_name][:, 1] = 255 if on else 0
        sums[op][ctrl_name][:, 2] = 255 if on else 0
    elif op == "Violet":
        sums[op][ctrl_name][:, 0] = 255 if on else 0
        sums[op][ctrl_name][:, 2] = 255 if on else 0
    elif op == "Bright":
        sums[op][ctrl_name][:, 2] = 50 if on else 0
    elif op == "Dark":
        sums[op][ctrl_name][:, 2] = 50 if on else 0
    elif op == "White":
        sums[op][ctrl_name][:, :] = 255 if on else 0
    elif op == "Black":
        sums[op][ctrl_name][:, :] = -255 if on else 0
    elif op == "Rainbow":
        rainbow_array = sums[op][ctrl_name]
        for i in range(PIXEL_COUNT):
            rainbow_array[i, :] = wheel(int(i * (256 / PIXEL_COUNT))) if on else 0
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


def do_cont_op(ctrl_name, op, value):
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


def update_pixels(pixels):
    pixels_json = [
        [int(pixels[i, 0]), int(pixels[i, 1]), int(pixels[i, 2])]
        for i in range(PIXEL_COUNT)
    ]

    requests.post("http://localhost:5000/pixels/rgb", json=pixels_json)


# -----------------------------------------------------------------------------


def main():
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARN)

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
