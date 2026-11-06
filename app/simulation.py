"""Wing shapes, and running the Fortran solver. No GUI code here."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

SOLVER = Path(__file__).resolve().parent.parent / "solver" / "windtunnel"

# Above this the solver gets slower, and on a SpacemiT K3 extra threads would
# land on the slower AI cores. Set OMP_NUM_THREADS to override.
MAX_THREADS = 8

ELLIPSE = 1
AEROFOIL = 2


def ellipse_outline(a, b):
    xu = np.linspace(-a, a, 100)
    xd = np.flipud(xu)
    yu = b * np.sqrt(1 - (xu / a) ** 2)
    yd = -b * np.sqrt(1 - (xd / a) ** 2)
    return np.append(xu, xd), np.append(yu, yd)


def aerofoil_outline(m, t):
    """Outline of a NACA 4-digit style aerofoil with camber m and thickness t."""
    p = 0.4
    c = 2.0

    xl = np.linspace(0, p * c, 40)
    xu = np.linspace(p * c, c, 60)
    x = np.append(xl, xu)
    xc = x / c
    xlc = xl / c
    xuc = xu / c

    yt = 5 * t * (0.2969 * np.sqrt(xc) - 0.1260 * xc - 0.3516 * xc**2 + 0.2843 * xc**3 - 0.1015 * xc**4)

    # Matches the solver, which deliberately bends the formula for large m and t
    ycl = m * xl / p / p * (2 * p - xlc)
    ycu = m * (c - xu) / (1 - p) / (1 - p) * (1 + xuc - 2 * p)
    yc = np.append(ycl, ycu)

    theta = np.arctan(np.append(2 * m / p / p * (p - xlc), 2 * m / (1 - p) ** 2 * (p - xuc)))

    upper = yc + yt * np.cos(theta)
    lower = yc - yt * np.cos(theta)
    return np.append(x, np.flipud(x)) - 1.0, np.append(upper, np.flipud(lower))


def rotate(x, y, degrees):
    """Rotate an outline for an angle of attack (positive is nose up)."""
    theta = np.radians(-degrees)
    return x * np.cos(theta) - y * np.sin(theta), y * np.cos(theta) + x * np.sin(theta)


def solver_config(shape, alpha, first, second):
    """Solver input. first and second are a and b for an ellipse, m and t for an aerofoil."""
    names = ("A", "B") if shape == ELLIPSE else ("M", "T")
    return (
        "&SHAPEPARAMS\n"
        f"SHAPE= {shape},\n"
        f"ALPHA= {alpha:f},\n"
        f"{names[0]}= {first:f},\n"
        f"{names[1]}= {second:f},\n"
        "/\n"
        "&VORTPARAMS\n"
        "VORTICITY= .FALSE.\n"
        "/\n"
    )


class Results:
    """Contents of a solver output file."""

    def __init__(self, path):
        with open(path, "rb") as f:
            nx, ny = np.fromfile(f, np.int32, 2)
            x = np.fromfile(f, np.float32, nx)
            y = np.fromfile(f, np.float32, ny)

            def field(dtype=np.float32):
                return np.fromfile(f, dtype, nx * ny).reshape(ny, nx)

            field()  # stream function
            field(np.int32)  # mask
            self.u = field()
            self.v = field()
            self.speed = field()
            self.pressure = field()
            field()  # vorticity

            forces = np.fromfile(f, np.float32, 6)
            self.lift, self.drag = forces[4], forces[5]
            self.c_lift, self.c_drag, self.c_lift_area, self.c_drag_area = np.fromfile(f, np.float32, 4)

        # The grid is uniform. Rebuild it from Python floats as float32 rounding
        # fails the even-spacing check in matplotlib's streamplot.
        self.x = np.linspace(float(x[0]), float(x[-1]), int(nx))
        self.y = np.linspace(float(y[0]), float(y[-1]), int(ny))


class SolverRun:
    """Runs the solver in the background. Poll finished(), then call results()."""

    def __init__(self, config):
        self.workdir = tempfile.mkdtemp(prefix="wing-demo-")
        (Path(self.workdir) / "config.txt").write_text(config)

        env = dict(os.environ)
        env.setdefault("OMP_NUM_THREADS", str(min(MAX_THREADS, os.cpu_count() or 1)))

        self.output = open(Path(self.workdir) / "solver.log", "wb")
        self.process = subprocess.Popen(
            [str(SOLVER)], cwd=self.workdir, env=env, stdout=self.output, stderr=subprocess.STDOUT
        )

    def finished(self):
        return self.process.poll() is not None

    def results(self):
        """Returns the results and removes the temporary files."""
        try:
            if self.process.returncode != 0:
                log = (Path(self.workdir) / "solver.log").read_text(errors="replace")
                raise RuntimeError(f"Solver failed ({self.process.returncode}):\n{log[-500:]}")
            return Results(Path(self.workdir) / "potential.dat")
        finally:
            self.cleanup()

    def cleanup(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        self.output.close()
        shutil.rmtree(self.workdir, ignore_errors=True)
