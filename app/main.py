"""Wing design wind tunnel demo. Run this file to start the app."""
import datetime
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import simulation
from range_window import RangeWindow
from simulation import AEROFOIL, ELLIPSE
from takeoff_window import TakeoffWindow
from timers import Timers

LOG_DIR = Path.home() / ".local" / "share" / "wing-demo"

GREEN = "#00ff00"
AMBER = "#ffbf00"
RED = "#ff0000"


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

    def pack_forget(self):
        self.label.pack_forget()
        self.scale.pack_forget()


class WindTunnelApp:
    def __init__(self, root):
        self.root = root
        self.timers = Timers(root)
        self.log = RunLog().write
        self.solver = None
        self.results = None
        self.takeoff_window = None
        self.range_window = None
        self.started = 0.0

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

        self.run_button = ttk.Button(self.setup, text="Run Simulation", command=self.start_simulation)
        self.run_button.pack(fill="x", ipady=20)

        self.shape = tk.IntVar(value=AEROFOIL)
        shapes = ttk.LabelFrame(self.setup, text="Shape", padding=4)
        shapes.pack(fill="x", pady=10)
        self.shape_buttons = [
            ttk.Radiobutton(shapes, text=text, value=value, variable=self.shape, command=self.show_shape_controls)
            for text, value in (("Ellipse", ELLIPSE), ("Aerofoil", AEROFOIL))
        ]
        for button in self.shape_buttons:
            button.pack(side="left", padx=4)

        self.sliders_frame = ttk.Frame(self.setup)
        self.sliders_frame.pack(fill="x")
        self.angle = Slider(self.sliders_frame, -45, 45, 0, self.draw_shape)
        self.camber = Slider(self.sliders_frame, -30, 30, 0, self.draw_shape)
        self.thickness = Slider(self.sliders_frame, 0, 50, 10, self.draw_shape)
        self.axis_a = Slider(self.sliders_frame, 2, 10, 6, self.draw_shape)
        self.axis_b = Slider(self.sliders_frame, 2, 10, 6, self.draw_shape)

        self.reset_button = ttk.Button(self.setup, text="Reset Options", command=self.reset)
        self.reset_button.pack(side="bottom", fill="x", ipady=20)

        self.status = ttk.Label(self.setup)
        self.status.pack(side="bottom", pady=4)
        self.progress = ttk.Progressbar(self.setup, mode="indeterminate")

    def build_results_panel(self):
        self.results_panel = ttk.Frame(self.panel)

        self.takeoff_button = ttk.Button(self.results_panel, text="Take off", command=self.show_takeoff)
        self.takeoff_button.pack(fill="x", ipady=20)
        self.range_button = ttk.Button(self.results_panel, text="Range", command=self.show_range)
        self.range_button.pack(fill="x", ipady=20, pady=(4, 0))

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

    def show_setup(self):
        for window in (self.takeoff_window, self.range_window):
            if window is not None:
                window.close()
        self.results_panel.pack_forget()
        self.setup.pack(fill="both", expand=True)
        self.show_shape_controls()

    def show_shape_controls(self):
        for slider in (self.angle, self.camber, self.thickness, self.axis_a, self.axis_b):
            slider.pack_forget()
        self.angle.pack()
        if self.shape.get() == ELLIPSE:
            self.axis_a.pack()
            self.axis_b.pack()
        else:
            self.camber.pack()
            self.thickness.pack()
        self.draw_shape()

    def reset(self):
        self.angle.scale.set(0)
        self.axis_a.scale.set(6)
        self.axis_b.scale.set(6)
        self.camber.scale.set(0)
        self.thickness.scale.set(2)
        self.draw_shape()

    def set_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in (self.run_button, self.reset_button, *self.shape_buttons):
            widget.configure(state=state)
        for slider in (self.angle, self.camber, self.thickness, self.axis_a, self.axis_b):
            slider.scale.configure(state=state)

    # ---- Shape preview ----

    def shape_values(self):
        """The two shape parameters, in metres or as a fraction of the chord."""
        if self.shape.get() == ELLIPSE:
            return self.axis_a.value * 0.1, self.axis_b.value * 0.1
        return self.camber.value * 0.01, self.thickness.value * 0.01 + 0.1

    def draw_shape(self):
        if not hasattr(self, "progress"):
            return  # sliders fire while they are being built

        first, second = self.shape_values()
        degrees = self.angle.value
        self.angle.label.configure(text=f"Angle = {degrees} degrees")

        self.figure.clf()
        self.axes = self.figure.add_subplot(111)

        if self.shape.get() == ELLIPSE:
            self.axis_a.label.configure(text=f"Red Axis = {first:3.1f}")
            self.axis_b.label.configure(text=f"Blue Axis = {second:3.1f}")
            x, y = simulation.ellipse_outline(first, second)
            self.axes.plot(*simulation.rotate(np.array([-first, first]), np.zeros(2), degrees), color="red")
            self.axes.plot(*simulation.rotate(np.zeros(2), np.array([-second, second]), degrees), color="blue")
        else:
            self.camber.label.configure(text=f"Camber    = {first:4.2f}")
            self.thickness.label.configure(text=f"Thickness = {second:3.2f}")
            x, y = simulation.aerofoil_outline(first, second)

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

        shape = self.shape.get()
        first, second = self.shape_values()
        alpha = float(self.angle.value)

        self.log("* New Simulation")
        self.log("    Time= " + datetime.datetime.now().strftime("%H:%M:%S"))
        self.log(f"    alpha= {alpha}")
        if shape == AEROFOIL:
            self.log(f"    m= {first}")
            self.log(f"    t= {second}")
        else:
            self.log(f"    a= {first}")
            self.log(f"    b= {second}")

        self.draw_decomposition()
        self.set_controls_enabled(False)
        self.status.configure(text="Calculating airflow...")
        self.progress.pack(side="bottom", fill="x")

        self.started = time.monotonic()
        self.solver = simulation.SolverRun(simulation.solver_config(shape, alpha, first, second))
        self.timers.after(50, self.check_solver)

    def check_solver(self):
        if self.solver is None:
            return
        if not self.solver.finished():
            self.progress.step(4)
            self.timers.after(50, self.check_solver)
            return

        solver, self.solver = self.solver, None
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
        r = self.results
        self.takeoff_window = TakeoffWindow(self.root, self.timers, r.c_lift_area, r.c_drag_area, self.log, self.takeoff_closed)

    def takeoff_closed(self):
        self.takeoff_window = None
        self.takeoff_button.configure(state="normal")

    def show_range(self):
        self.range_button.configure(state="disabled")
        r = self.results
        self.range_window = RangeWindow(self.root, self.timers, r.c_lift_area, r.c_drag_area, self.log, self.range_closed)

    def range_closed(self):
        self.range_window = None
        self.range_button.configure(state="normal")

    def close(self):
        if self.solver is not None:
            self.solver.cleanup()
        self.root.destroy()


def main():
    root = tk.Tk()
    WindTunnelApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
