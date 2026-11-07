"""Wing design wind tunnel demo. Run this file to start the app."""
import argparse
import datetime
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import simulation
from cpu_window import CpuWindow
from range_window import RangeWindow
from takeoff_window import TakeoffWindow
from timers import Timers

LOG_DIR = Path.home() / ".local" / "share" / "wing-demo"

GREEN = "#00ff00"
AMBER = "#ffbf00"
RED = "#ff0000"

HEADING_FONT = ("TkDefaultFont", 13, "bold")
SIMULATE_COLOUR = "#6a3d9a"
TAKEOFF_COLOUR = "#1b7f3b"
RANGE_COLOUR = "#1f5fa8"
FLASH_COLOUR = "#ffbf00"
FLASH_MS = 500

MIN_ACCURACY = 0.1
MAX_ACCURACY = 4.0


class RunLog:
    """Appends a record of each simulation to a daily log file."""

    def write(self, line):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / f"{datetime.date.today()}.log", "a") as f:
            f.write(line + "\n")


class Slider:
    def __init__(self, parent, low, high, value, command):
        self.label = ttk.Label(parent)
        self.scale = tk.Scale(
            parent, from_=low, to=high, orient="horizontal", showvalue=False, command=lambda _: command()
        )
        self.scale.set(value)

    @property
    def value(self):
        return self.scale.get()

    def pack(self):
        self.label.pack(anchor="w", pady=(8, 0))
        self.scale.pack(fill="x")


class WindTunnelApp:
    def __init__(self, root, accuracy=1.0):
        self.root = root
        self.accuracy = accuracy
        self.timers = Timers(root)
        self.log = RunLog().write
        self.solver = None
        self.results = None
        self.takeoff_window = None
        self.range_window = None
        self.cpu_window = None
        self.started = 0.0
        self.next_steps = []  # buttons not yet tried, the first of which flashes
        self.flash_timer = None

        root.title("Windtunnel Simulator")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.iconphoto(True, tk.PhotoImage(file=Path(__file__).parent / "assets" / "icon.png"))

        self.panel = ttk.Frame(root, width=270, padding=6)
        self.panel.pack(side="left", fill="y")
        self.panel.pack_propagate(False)

        self.figure = Figure(figsize=(8, 6))
        self.canvas = FigureCanvasTkAgg(self.figure, master=root)
        self.canvas.get_tk_widget().pack(side="right", fill="both", expand=True)

        self.build_setup_panel()
        self.build_results_panel()
        self.show_setup()

    # ---- Controls ----

    def build_setup_panel(self):
        self.setup = ttk.Frame(self.panel)

        self.heading(self.setup, "1. Design your wing")

        sliders = ttk.Frame(self.setup)
        sliders.pack(fill="x", pady=(0, 20))
        self.angle = Slider(sliders, -45, 45, 0, self.draw_shape)
        self.camber = Slider(sliders, -30, 30, 0, self.draw_shape)
        self.thickness = Slider(sliders, 0, 50, 10, self.draw_shape)
        for slider in (self.angle, self.camber, self.thickness):
            slider.pack()

        self.heading(self.setup, "When you are happy with your wing:")
        self.run_button = self.step_button(self.setup, "2. Simulate", SIMULATE_COLOUR, self.start_simulation)

        self.reset_button = ttk.Button(self.setup, text="Reset Options", command=self.reset)
        self.reset_button.pack(side="bottom", fill="x", ipady=20)

        self.status = ttk.Label(self.setup)
        self.status.pack(side="bottom", pady=4)
        self.progress = ttk.Progressbar(self.setup, mode="indeterminate")

    def build_results_panel(self):
        self.results_panel = ttk.Frame(self.panel)

        self.heading(self.results_panel, "Simulation finished!\nNow find out if your wing can fly:")

        self.takeoff_button = self.step_button(self.results_panel, "3. Take off", TAKEOFF_COLOUR, self.show_takeoff)
        self.range_button = self.step_button(self.results_panel, "4. Range", RANGE_COLOUR, self.show_range)

        self.view = tk.StringVar(value="flow")
        views = ttk.LabelFrame(self.results_panel, text="Variable", padding=4)
        views.pack(fill="x", pady=20)
        for text, value in (("Flow", "flow"), ("Pressure", "pressure")):
            ttk.Radiobutton(views, text=text, value=value, variable=self.view, command=self.draw_results).pack(
                side="left", padx=4
            )

        self.summary = tk.Text(self.results_panel, height=3, width=20, state="disabled", cursor="arrow")
        self.summary.pack(side="bottom", fill="x", pady=(4, 0))
        for name, colour in (("green", GREEN), ("amber", AMBER), ("red", RED)):
            self.summary.tag_configure(name, background=colour, foreground="black")

        ttk.Button(self.results_panel, text="New Simulation", command=self.show_setup).pack(
            side="bottom", fill="x", ipady=20
        )

    def heading(self, parent, text):
        ttk.Label(parent, text=text, font=HEADING_FONT, justify="center", anchor="center", wraplength=250).pack(
            fill="x", pady=(4, 10)
        )

    def step_button(self, parent, text, colour, command):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=("TkDefaultFont", 18, "bold"),
            background=colour,
            activebackground=colour,
            foreground="white",
            activeforeground="white",
            borderwidth=3,
        )
        button.colour = colour
        button.pack(fill="x", ipady=18, pady=(0, 6))
        return button

    def flash_next_step(self, lit=True):
        """Flash the next button to press, so that nobody stops at the airflow plot."""
        self.stop_flashing()
        if self.next_steps:
            button = self.next_steps[0]
            colour = FLASH_COLOUR if lit else button.colour
            button.configure(background=colour, activebackground=colour, foreground="black" if lit else "white")
            self.flash_timer = self.timers.after(FLASH_MS, lambda: self.flash_next_step(not lit))

    def stop_flashing(self):
        if self.flash_timer is not None:
            self.timers.cancel(self.flash_timer)
            self.flash_timer = None
        for button in (self.takeoff_button, self.range_button):
            button.configure(background=button.colour, activebackground=button.colour, foreground="white")

    def step_done(self, button):
        if button in self.next_steps:
            self.next_steps.remove(button)
        self.flash_next_step()

    def show_setup(self):
        self.next_steps = []
        self.stop_flashing()
        for window in (self.takeoff_window, self.range_window):
            if window is not None:
                window.close()
        self.results_panel.pack_forget()
        self.setup.pack(fill="both", expand=True)
        self.draw_shape()

    def reset(self):
        self.angle.scale.set(0)
        self.camber.scale.set(0)
        self.thickness.scale.set(2)
        self.draw_shape()

    def set_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in (self.run_button, self.reset_button):
            widget.configure(state=state)
        for slider in (self.angle, self.camber, self.thickness):
            slider.scale.configure(state=state)

    # ---- Shape preview ----

    def shape_values(self):
        """Camber and thickness as a fraction of the chord."""
        return self.camber.value * 0.01, self.thickness.value * 0.01 + 0.1

    def draw_shape(self):
        if not hasattr(self, "progress"):
            return  # sliders fire while they are being built

        camber, thickness = self.shape_values()
        degrees = self.angle.value
        self.angle.label.configure(text=f"Angle = {degrees} degrees")
        self.camber.label.configure(text=f"Camber    = {camber:4.2f}")
        self.thickness.label.configure(text=f"Thickness = {thickness:3.2f}")

        self.figure.clf()
        self.axes = self.figure.add_subplot(111)

        x, y = simulation.aerofoil_outline(camber, thickness)
        self.axes.plot(*simulation.rotate(x, y, degrees), color="black")
        self.axes.axis("equal")
        self.axes.set_xlim(-2.0, 2.0)
        self.axes.set_ylim(-2.0, 2.0)
        self.axes.set_xlabel("x (m)")
        self.axes.set_ylabel("y (m)")
        self.axes.set_aspect("equal", adjustable="box")

        # Arrows showing the direction of the airflow
        for x0, y0 in ((-1.5, -1.5), (-1.5, 1.5), (0.5, -1.5), (0.5, 1.5)):
            self.axes.arrow(x0, y0, 1.0, 0.0, lw=1, head_width=0.1, color="black")

        self.canvas.draw_idle()

    def draw_decomposition(self):
        """Dashed lines showing how the grid is shared out between processors."""
        for position in (-2.0, -1.0, 0.0, 1.0):
            self.axes.plot([position, position], [-2.0, 2.0], color="black", linestyle="dashed")
            self.axes.plot([-2.0, 2.0], [position, position], color="black", linestyle="dashed")
        self.canvas.draw_idle()

    # ---- Running the solver ----

    def start_simulation(self):
        if not simulation.SOLVER.exists():
            messagebox.showerror("Solver not found", "The solver has not been built. Please run ./install.sh")
            return

        camber, thickness = self.shape_values()
        alpha = float(self.angle.value)

        self.log("* New Simulation")
        self.log("    Time= " + datetime.datetime.now().strftime("%H:%M:%S"))
        self.log(f"    alpha= {alpha}")
        self.log(f"    m= {camber}")
        self.log(f"    t= {thickness}")

        self.draw_decomposition()
        self.set_controls_enabled(False)
        self.status.configure(text="Calculating airflow...")
        self.progress.pack(side="bottom", fill="x")

        if self.cpu_window is not None:
            self.cpu_window.close()
        self.cpu_window = CpuWindow(
            self.root, self.timers, simulation.solver_threads(), simulation.solver_cpus(), self.cpu_closed
        )

        self.started = time.monotonic()
        self.solver = simulation.SolverRun(simulation.solver_config(alpha, camber, thickness, self.accuracy))
        self.timers.after(50, self.check_solver)

    def cpu_closed(self):
        self.cpu_window = None

    def check_solver(self):
        if self.solver is None:
            return
        if not self.solver.finished():
            self.progress.step(4)
            self.timers.after(50, self.check_solver)
            return

        solver, self.solver = self.solver, None
        if self.cpu_window is not None:
            self.cpu_window.finish()
        self.progress.pack_forget()
        self.status.configure(text="")
        self.set_controls_enabled(True)

        try:
            self.results = solver.results()
        except (RuntimeError, OSError, ValueError) as error:
            messagebox.showerror("Simulation failed", str(error))
            self.draw_shape()
            return

        r = self.results
        self.log(f"    Time to Complete = {time.monotonic() - self.started}")
        self.log(f"    Lift= {r.lift}")
        self.log(f"    Drag= {r.drag}")
        self.log(f"    Lift/drag= {r.lift / r.drag}")
        self.log(f"    Lift coeff= {r.c_lift}")
        self.log(f"    Drag coeff= {r.c_drag}")

        self.setup.pack_forget()
        self.results_panel.pack(fill="both", expand=True)
        self.draw_results()
        self.next_steps = [self.takeoff_button, self.range_button]
        self.flash_next_step()

    # ---- Results ----

    def draw_results(self):
        r = self.results
        extent = (r.x[0], r.x[-1], r.y[0], r.y[-1])

        self.figure.clf()
        axes = self.figure.add_subplot(111)

        if self.view.get() == "flow":
            image = axes.imshow(r.speed, origin="lower", extent=extent)
            axes.streamplot(r.x, r.y, r.u, r.v, density=1.25, arrowstyle="->", color="black")
            self.figure.colorbar(image).set_label("Velocity (kmph)")
            axes.axis("equal")
            axes.set_title("Flowlines")
            axes.set_xlim(r.x[0], r.x[-1])
            axes.set_ylim(r.y[0], r.y[-1])
        else:
            image = axes.imshow(r.pressure, origin="lower", extent=extent)
            self.figure.colorbar(image)
            axes.axis("equal")
            axes.set_title("Pressure")

        # Arrow showing the direction of the total force on the wing
        total = np.sqrt(r.lift**2 + r.drag**2)
        axes.arrow(0.0, 0.0, r.drag / total, r.lift / total, shape="full", lw=3, head_width=0.1)

        self.canvas.draw_idle()
        self.show_summary()

    def show_summary(self):
        lift = self.results.lift / 1000
        drag = self.results.drag / 1000
        ratio = lift / drag

        def rating(good, ok):
            return "green" if good else "amber" if ok else "red"

        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("end", f"Lift= {lift:6.1f} kN \n", rating(lift > 1, lift > 0.2))
        self.summary.insert("end", f"Drag= {drag:6.1f} kN \n", rating(drag < 0.2, drag < 1.0))
        self.summary.insert("end", f"lift/drag= {ratio:6.3f}", rating(ratio > 10, ratio > 2.0))
        self.summary.configure(state="disabled")

    def show_takeoff(self):
        self.takeoff_button.configure(state="disabled")
        self.step_done(self.takeoff_button)
        r = self.results
        self.takeoff_window = TakeoffWindow(
            self.root, self.timers, r.c_lift_area, r.c_drag_area, self.log, self.takeoff_closed, self.takeoff_finished
        )

    def takeoff_finished(self):
        if self.range_window is None:
            self.show_range()

    def takeoff_closed(self):
        self.takeoff_window = None
        self.takeoff_button.configure(state="normal")

    def show_range(self):
        self.range_button.configure(state="disabled")
        self.step_done(self.range_button)
        r = self.results
        self.range_window = RangeWindow(self.root, self.timers, r.c_lift_area, r.c_drag_area, self.log, self.range_closed)

    def range_closed(self):
        self.range_window = None
        self.range_button.configure(state="normal")

    def close(self):
        if self.solver is not None:
            self.solver.cleanup()
        if self.cpu_window is not None:
            self.cpu_window.close()
        self.root.destroy()


def accuracy_value(text):
    value = float(text)
    if not MIN_ACCURACY <= value <= MAX_ACCURACY:
        raise argparse.ArgumentTypeError(f"must be between {MIN_ACCURACY} and {MAX_ACCURACY}")
    return value


def main():
    parser = argparse.ArgumentParser(description="Design a wing and test it in a simulated wind tunnel.")
    parser.add_argument(
        "--accuracy",
        type=accuracy_value,
        default=1.0,
        help="scales the solver's grid and iterations (default 1). Run time grows with the "
        "fourth power of this, so 2 takes about 16 times as long and 0.5 about a sixteenth.",
    )
    args = parser.parse_args()

    root = tk.Tk()
    WindTunnelApp(root, args.accuracy)
    root.mainloop()


if __name__ == "__main__":
    main()
