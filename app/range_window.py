"""The range map: shows how far the plane can reach as its fuel runs down."""
import math
import tkinter as tk
from pathlib import Path

import matplotlib.image
import numpy as np

from flight import MAP_HEIGHT, MAP_WIDTH, EARTH_RADIUS, flight_range, map_angles

ASSETS = Path(__file__).resolve().parent / "assets"

FRAME_MS = 10
FUEL_FULL = 125.0  # fuel needle angle in degrees, sweeping to -FUEL_FULL when empty
FUEL_STEP = 0.5

# Colour of each tenth of the range, near to far, as a share of the fuel used
BAND_COLOURS = np.array([(0, 255, 0)] * 7 + [(255, 165, 0)] * 2 + [(255, 0, 0)], dtype=float)
BAND_ALPHA = 0.3

# Fuel needle angles at which each band appears
BAND_REVEALS = {124.5: 1, 100: 2, 75: 3, 50: 4, 25: 5, 0: 6, -25: 7, -50: 8, -75: 9, -100: 10}

FUEL_CENTRE = (115, 315)
FUEL_NEEDLE_LENGTH = 60


class RangeWindow(tk.Toplevel):
    def __init__(self, parent, timers, c_lift, c_drag, log, on_close):
        super().__init__(parent)
        self.title("Range")
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.timers = timers
        self.on_close = on_close

        self.result = flight_range(c_lift, c_drag)
        log(f"    Cruise Speed = {self.result.speed_kmph} km/h")
        log(f"    Range = {self.result.km} km ")

        self.base = matplotlib.image.imread(ASSETS / "map.png")[:, :, :3] * 255.0
        self.bands = self.map_bands()

        self.canvas = tk.Canvas(self, width=MAP_WIDTH, height=MAP_HEIGHT, highlightthickness=0)
        self.canvas.pack()
        self.photo = None
        self.map_item = self.canvas.create_image(0, 0, anchor="nw")
        self.show_bands(0)

        self.needle = self.canvas.create_line(*FUEL_CENTRE, *FUEL_CENTRE, fill="red", width=2)
        self.clock = self.canvas.create_text(115, 442, fill="white", font=("TkDefaultFont", 20))

        hours = math.floor(self.result.hours)
        minutes = (self.result.hours - hours) * 60.0
        self.canvas.create_text(
            600,
            425,
            anchor="nw",
            font=("TkDefaultFont", 15),
            text=f"Speed = {self.result.speed_kmph:.0f} kmph\n"
            f"Flight Time =  {hours} Hours {int(minutes)} Minutes \n"
            f"Range = {self.result.km:.0f} km",
        )

        self.fuel = FUEL_FULL
        self.time_passed = 0.0
        self.next_frame = None
        self.show_instruments()
        if self.result.can_fly:
            self.next_frame = self.timers.after(FRAME_MS, self.animate)

    def map_bands(self):
        """Which tenth of the range each map pixel falls in, or 10 if out of reach."""
        if not self.result.can_fly:
            return np.full((MAP_HEIGHT, MAP_WIDTH), 10)
        reach = self.result.km / EARTH_RADIUS
        angles = map_angles()
        return np.where(angles <= reach, np.minimum(angles / reach * 10, 9).astype(int), 10)

    def show_bands(self, count):
        """Draw the first count bands over the map."""
        image = self.base.copy()
        shown = self.bands < count
        colours = BAND_COLOURS[self.bands[shown]]
        image[shown] = image[shown] * (1 - BAND_ALPHA) + colours * BAND_ALPHA

        pixels = image.astype(np.uint8).tobytes()
        ppm = b"P6\n%d %d\n255\n" % (MAP_WIDTH, MAP_HEIGHT) + pixels
        self.photo = tk.PhotoImage(data=ppm, format="PPM", master=self.canvas)
        self.canvas.itemconfigure(self.map_item, image=self.photo)

    def show_instruments(self):
        angle = math.radians(self.fuel)
        self.canvas.coords(
            self.needle,
            *FUEL_CENTRE,
            FUEL_CENTRE[0] + math.sin(angle) * FUEL_NEEDLE_LENGTH,
            FUEL_CENTRE[1] - math.cos(angle) * FUEL_NEEDLE_LENGTH,
        )
        hours = int(self.time_passed)
        minutes = int((self.time_passed - hours) * 60)
        self.canvas.itemconfigure(self.clock, text=f"{hours:02d}:{minutes:02d}")

    def animate(self):
        self.fuel -= FUEL_STEP
        self.time_passed += self.result.hours / 500
        self.show_instruments()

        if self.fuel in BAND_REVEALS:
            self.show_bands(BAND_REVEALS[self.fuel])

        if self.fuel > -FUEL_FULL:
            self.next_frame = self.timers.after(FRAME_MS, self.animate)
        else:
            self.next_frame = None

    def close(self):
        if self.next_frame is not None:
            self.timers.cancel(self.next_frame)
        self.on_close()
        self.destroy()
