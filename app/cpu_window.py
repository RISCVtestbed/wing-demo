"""A window showing the load on each CPU while the solver runs."""
import tkinter as tk
from pathlib import Path

SAMPLE_MS = 200  # the kernel counts CPU time in 10 ms steps, so much faster is noisy
HOLD_MS = 2000  # stay open after the solver finishes, as a run can take under a second

BAR_COLOUR = "#6a3d9a"
TROUGH_COLOUR = "#e4e4e4"
BAR_WIDTH = 46
BAR_HEIGHT = 150
GAP = 10
LABEL_HEIGHT = 20  # room for the text above and below a bar
MAX_COLUMNS = 16


def read_cpu_times(path="/proc/stat"):
    """Busy and total time so far, in clock ticks, for each CPU by name."""
    times = {}
    for line in Path(path).read_text().splitlines():
        name, *fields = line.split()
        if name.startswith("cpu") and name != "cpu":
            values = [int(field) for field in fields[:8]]
            idle = values[3] + values[4]  # idle and waiting for disk
            times[name] = (sum(values) - idle, sum(values))
    return times


def cpu_loads(before, after):
    """Fraction of the time each CPU was busy between two read_cpu_times() calls."""
    loads = {}
    for name, (busy, total) in after.items():
        old_busy, old_total = before.get(name, (busy, total))
        elapsed = total - old_total
        loads[name] = min(max((busy - old_busy) / elapsed, 0.0), 1.0) if elapsed > 0 else 0.0
    return loads


class CpuWindow(tk.Toplevel):
    def __init__(self, parent, timers, threads, on_close):
        super().__init__(parent)
        self.timers = timers
        self.on_close = on_close
        self.title("CPU load")
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.geometry(f"+{parent.winfo_rootx() + 290}+{parent.winfo_rooty() + 30}")

        self.times = read_cpu_times()
        self.columns = min(len(self.times), MAX_COLUMNS)
        rows = -(-len(self.times) // self.columns)
        cell_width = BAR_WIDTH + GAP
        cell_height = BAR_HEIGHT + 2 * LABEL_HEIGHT

        self.caption = tk.Label(self, text=f"Load on each CPU: simulating on {threads} threads...", font=("TkDefaultFont", 13, "bold"))
        self.caption.pack(pady=(8, 0))
        self.canvas = tk.Canvas(
            self,
            width=self.columns * cell_width + GAP,
            height=rows * cell_height,
            background="white",
            highlightthickness=0,
        )
        self.canvas.pack(padx=8, pady=8)

        self.bars = {}  # CPU name to (bar, percentage text, bar left, bar bottom)
        for index, name in enumerate(self.times):
            left = GAP + index % self.columns * cell_width
            top = index // self.columns * cell_height + LABEL_HEIGHT
            bottom = top + BAR_HEIGHT
            middle = left + BAR_WIDTH / 2

            self.canvas.create_rectangle(left, top, left + BAR_WIDTH, bottom, fill=TROUGH_COLOUR, outline="")
            bar = self.canvas.create_rectangle(left, bottom, left + BAR_WIDTH, bottom, fill=BAR_COLOUR, outline="")
            text = self.canvas.create_text(middle, top - LABEL_HEIGHT / 2, text="0%")
            self.canvas.create_text(middle, bottom + LABEL_HEIGHT / 2, text=f"CPU {name[3:]}")
            self.bars[name] = (bar, text, left, bottom)

        self.hold_timer = None
        self.next_sample = self.timers.after(SAMPLE_MS, self.sample)

    def sample(self):
        times = read_cpu_times()
        loads = cpu_loads(self.times, times)
        self.times = times

        for name, (bar, text, left, bottom) in self.bars.items():
            load = loads.get(name, 0.0)
            self.canvas.coords(bar, left, bottom - load * BAR_HEIGHT, left + BAR_WIDTH, bottom)
            self.canvas.itemconfigure(text, text=f"{load:.0%}")

        self.next_sample = self.timers.after(SAMPLE_MS, self.sample)

    def finish(self):
        """The solver has stopped: show the load falling, then close."""
        self.caption.configure(text="Load on each CPU: simulation finished")
        self.hold_timer = self.timers.after(HOLD_MS, self.close)

    def close(self):
        self.timers.cancel(self.next_sample)
        if self.hold_timer is not None:
            self.timers.cancel(self.hold_timer)
        self.on_close()
        self.destroy()
