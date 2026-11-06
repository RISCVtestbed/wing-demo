# Wing Demo

Design a wing, test it in a simulated wind tunnel, then find out whether a plane with that wing can take off and how far it can fly.

The airflow is calculated by a parallel Fortran solver that uses every core available to it (up to 8 by default), so the demo also shows what parallel computing can do.

## Install

You need Ubuntu (24.04 or later) on any machine, including RISC-V. Download this repository, open a terminal in its folder, and run:

```bash
./install.sh
```

## Run

Open **Wing Demo** from your applications menu, or run:

```bash
./wing-demo
```

To trade accuracy against speed, add `--accuracy`. It scales the solver's grid and number of iterations, and the default is 1:

```bash
./wing-demo --accuracy 2     # finer, takes about 16 times as long
./wing-demo --accuracy 0.5   # coarser, takes about a sixteenth of the time
```

## Using the demo

1. Use the sliders to design your wing.
2. Press **2. Simulate** to see how air flows around it, with a bar for each CPU showing its load while it runs, then switch between **Flow** and **Pressure**.
3. Press **3. Take off** to see if the plane leaves the runway, with the cockpit dashboard alongside.
4. The range map then opens by itself to show how far it can fly on a tank of fuel. Press **4. Range** to see it again.
5. Press **New Simulation** to try to do better.

Each simulation is recorded in a daily log in `~/.local/share/wing-demo/`.

## For developers

| Path | Contents |
| --- | --- |
| `solver/` | Fortran and OpenMP flow solver. Reads `config.txt` and writes binary results to the current folder. |
| `wing-demo` | Launcher. Always uses the system Python, so an active venv or conda environment can't get in the way. |
| `app/main.py` | Main window. |
| `app/simulation.py` | Wing shapes, running the solver, reading its results. |
| `app/flight.py` | Take-off and range physics. |
| `app/takeoff_window.py` | Runway animation and dashboard. |
| `app/range_window.py` | Range map. |
| `app/cpu_window.py` | Load on each CPU while the solver runs, read from `/proc/stat`. |
| `app/timers.py` | Timers that survive system clock changes. Use these rather than Tk's `after()`, which freezes if the clock steps backwards. |

The solver uses up to 8 threads. Set `OMP_NUM_THREADS` to change this.

To run the tests, from this folder:

```bash
make -C solver
/usr/bin/python3 -s -m unittest discover tests
```

## Credits

Extracted from [Wee Archie](https://github.com/EPCCed/wee_archie), the EPCC outreach supercomputer. The original demo framework was written by Gordon Gibb and Alistair Grant, the CFD demo by Gordon Gibb and the artwork by Mirren White. Kara Moraw added enhancements under a PRACE Summer of HPC 2017 visit.

Licensed under the licence of the original code: see `LICENSE`.

The RISC-V logo on the take-off screen is a trademark of RISC-V International.
