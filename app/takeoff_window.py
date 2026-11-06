"""The take-off animation and cockpit dashboard."""
import math
import time
import tkinter as tk
from pathlib import Path

from flight import TakeoffRun, crash_message, takeoff_message

ASSETS = Path(__file__).resolve().parent / "assets"

TICK_SECONDS = 0.01  # physics rate, independent of how fast we can draw
FRAME_MS = 20  # how often we try to redraw
MAX_TICKS_PER_FRAME = 20
OFFSCREEN = (-1000, -1000)
TAKEOFF_TEXT = "#1b7f3b"
CRASH_TEXT = "#d00000"


class Sprites:
    """Canvas items that are only touched when they actually change."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.images = {}
        self.positions = {}

    def add(self, filename, position=OFFSCREEN):
        image = self.image(filename)
        item = self.canvas.create_image(*position, image=image, anchor="nw")
        self.positions[item] = position
        return item

    def image(self, filename):
        if filename not in self.images:
            self.images[filename] = tk.PhotoImage(file=ASSETS / filename, master=self.canvas)
        return self.images[filename]

    def move(self, item, position):
        if self.positions.get(item) != position:
            self.positions[item] = position
            self.canvas.coords(item, *position)


class Needle:
    """A dial pointer. scale is (degrees, value) so that value maps to that many degrees."""

    def __init__(self, canvas, centre, scale, length, colour):
        self.canvas = canvas
        self.centre = centre
        self.scale = scale
        self.length = length
        self.end = None
        self.item = canvas.create_line(*centre, *centre, fill=colour, width=2)

    def show(self, value):
        angle = math.radians(value * self.scale[0] / self.scale[1])
        end = (
            int(self.centre[0] + math.sin(angle) * self.length),
            int(self.centre[1] - math.cos(angle) * self.length),
        )
        if end != self.end:
            self.end = end
            self.canvas.coords(self.item, *self.centre, *end)


class Dashboard(tk.Toplevel):
    def __init__(self, parent, critical_speed):
        super().__init__(parent)
        self.title("Dashboard")
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # closes with the runway window

        self.canvas = tk.Canvas(self, width=840, height=270, highlightthickness=0)
        self.canvas.pack()
        self.sprites = Sprites(self.canvas)

        self.sprites.add("dashboard.png", (0, 0))
        self.black_left = self.sprites.add("dashboard_black_l.png")
        self.black_right = self.sprites.add("dashboard_black_r.png")
        self.red_left = self.sprites.add("dashboard_red_l.png")
        self.red_right = self.sprites.add("dashboard_red_r.png")
        self.attitude = self.sprites.add("attitude_bg.png")
        self.attitude_ring = self.sprites.add("attitude_ring.png")

        self.critical = Needle(self.canvas, (260, 65), (1, 1), 60, "red")
        self.speed = Needle(self.canvas, (260, 65), (1, 1), 33, "green")
        self.altitude_hundreds = Needle(self.canvas, (563, 65), (90, 250), 40, "grey")
        self.altitude_tens = Needle(self.canvas, (563, 65), (90, 25), 30, "light grey")
        self.vertical_speed = Needle(self.canvas, (560, 195), (90, 125), 30, "cyan")

        self.critical.show(critical_speed)

    def show(self, run):
        if run.touchdown:
            self.sprites.move(self.black_left, (0, 0))
            self.sprites.move(self.black_right, (640, 0))
            lights = run.warning_lights_on
            self.sprites.move(self.red_left, (1, 0) if lights else OFFSCREEN)
            self.sprites.move(self.red_right, (631, 0) if lights else OFFSCREEN)
            return

        tens, hundreds, speed, vertical_speed = run.dials
        self.altitude_tens.show(tens)
        self.altitude_hundreds.show(hundreds)
        self.speed.show(speed)
        self.vertical_speed.show(vertical_speed)

        if run.attitude_ticks > 0:
            self.sprites.move(self.attitude, (360, 13 + min(run.attitude_ticks, 12)))
            self.sprites.move(self.attitude_ring, (350, 5))


class TakeoffWindow(tk.Toplevel):
    def __init__(self, parent, timers, c_lift, c_drag, log, on_close, on_finished):
        super().__init__(parent)
        self.title("Runway")
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.timers = timers
        self.log = log
        self.on_close = on_close
        self.on_finished = on_finished
        self.run = TakeoffRun(c_lift, c_drag)
        self.crash_message = crash_message(c_lift, c_drag)
        self.message_shown = False

        self.canvas = tk.Canvas(self, width=1200, height=670, highlightthickness=0)
        self.canvas.pack()
        self.sprites = Sprites(self.canvas)

        self.sprites.add("background.png", (0, 0))
        self.splash = self.sprites.add("splash.png")
        self.plane = self.sprites.add("plane.png", (int(self.run.x), int(self.run.y)))
        self.water = self.sprites.add("water.png")
        self.rafts = [self.sprites.add("raft.png") for _ in self.run.rafts]

        self.geometry("+0+0")
        self.dashboard = Dashboard(self, self.run.critical_speed)
        self.place_dashboard()

        self.logged_outcome = False
        self.ticks = 0
        self.frames = 0
        self.started = time.monotonic()
        self.next_frame = self.timers.after(FRAME_MS, self.animate)

    def place_dashboard(self):
        """Under the runway window if there is room, else the bottom of the screen."""
        self.update_idletasks()
        top = min(self.winfo_rooty() + 700, self.winfo_screenheight() - 300)
        left = max(0, (min(self.winfo_screenwidth(), 1200) - 840) // 2)
        self.dashboard.geometry(f"+{left}+{max(0, top)}")

    def animate(self):
        due = int((time.monotonic() - self.started) / TICK_SECONDS) - self.ticks
        steps = min(due, MAX_TICKS_PER_FRAME)
        for _ in range(steps):
            self.run.tick()
        self.ticks += due  # if we fall a long way behind, drop time rather than lag

        self.draw()
        self.frames += 1
        self.log_outcome()

        if self.run.finished:
            self.next_frame = None
            self.on_finished()
        else:
            self.next_frame = self.timers.after(FRAME_MS, self.animate)

    def draw(self):
        run = self.run

        if run.airborne and not run.crash:
            self.canvas.itemconfigure(self.plane, image=self.sprites.image("plane_climbing.png"))
            if not self.message_shown:
                self.show_message(takeoff_message(run.runway_used), TAKEOFF_TEXT)
        self.sprites.move(self.plane, (int(run.x), int(run.y)))

        if run.crash and self.crash_message and not self.message_shown:
            self.show_message(self.crash_message, CRASH_TEXT)

        if run.touchdown:
            self.sprites.move(self.splash, (int(run.splash_x), 510))

        if run.counter > 50:
            for item, raft in zip(self.rafts, run.rafts):
                self.sprites.move(item, (int(raft.x), int(raft.y)))

        if run.counter > 100:
            self.sprites.move(self.water, (-25, int(run.waterlevel)))

        self.dashboard.show(run)

    def show_message(self, message, colour):
        text = self.canvas.create_text(600, 50, text=message, fill=colour, font=("TkDefaultFont", 22, "bold"))
        left, top, right, bottom = self.canvas.bbox(text)
        panel = self.canvas.create_rectangle(
            left - 16, top - 10, right + 16, bottom + 10, fill="white", outline=colour, width=3
        )
        self.canvas.tag_lower(panel, text)
        self.canvas.tag_raise(self.plane)  # the plane flies in front of the message
        self.message_shown = True

    def log_outcome(self):
        if self.logged_outcome:
            return
        if self.run.airborne:
            self.log("    Takeoff = True")
            self.log(f"    Runway Dist= {self.run.runway_used} m ")
            self.logged_outcome = True
        elif self.run.crash:
            self.log("    Takeoff = False")
            self.logged_outcome = True

    def close(self):
        if self.next_frame is not None:
            self.timers.cancel(self.next_frame)
        self.on_close()
        self.destroy()
