"""Checks the solver and flight physics against results from the original demo.

Run from the repository root with: /usr/bin/python3 -s -m unittest discover tests
"""
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import cpu_window
import flight
import range_window
import simulation
import takeoff_window
from timers import Timers


def solve(*config):
    run = simulation.SolverRun(simulation.solver_config(*config))
    while not run.finished():
        time.sleep(0.05)
    return run.results()


class Solver(unittest.TestCase):
    def test_aerofoil(self):
        r = solve(5.0, 0.05, 0.12)
        self.assertAlmostEqual(float(r.lift), 619.602417, places=2)
        self.assertAlmostEqual(float(r.drag), 36.7750778, places=3)
        self.assertAlmostEqual(float(r.c_lift), 0.638808906, places=5)


class Accuracy(unittest.TestCase):
    def test_default_is_the_standard_grid(self):
        self.assertIn("NX= 576,", simulation.solver_config(5.0, 0.05, 0.12))
        self.assertIn("ITERATIONS= 5000,", simulation.solver_config(5.0, 0.05, 0.12))

    def test_accuracy_scales_grid_and_iterations(self):
        config = simulation.solver_config(5.0, 0.05, 0.12, accuracy=0.5)
        self.assertIn("NY= 288,", config)
        self.assertIn("ITERATIONS= 1250,", config)

    def test_solver_uses_the_requested_grid(self):
        self.assertEqual(solve(5.0, 0.05, 0.12, 0.25).speed.shape, (144, 144))


class Range(unittest.TestCase):
    def test_range_of_a_good_wing(self):
        result = flight.flight_range(2.4528644, 0.15818255)
        self.assertTrue(result.can_fly)
        self.assertAlmostEqual(result.speed_kmph, 379.1727, places=2)
        self.assertAlmostEqual(result.km, 6941.2627, places=1)

    def test_no_lift_means_no_range(self):
        self.assertFalse(flight.flight_range(-1.0, 0.1).can_fly)

    def test_too_much_drag_means_no_range(self):
        self.assertFalse(flight.flight_range(0.00032337508, 0.04710259).can_fly)

    def test_airport_is_at_zero_angle(self):
        angles = flight.map_angles()
        self.assertLess(angles.min(), 0.01)


class Runway(unittest.TestCase):
    def test_good_wing_fits_the_runway(self):
        self.assertAlmostEqual(flight.runway_needed(2.4528644, 0.15818255), 1817.56, places=1)

    def test_weak_wing_needs_a_longer_runway(self):
        self.assertGreater(flight.runway_needed(1.05, 0.2), flight.RUNWAY_LENGTH)

    def test_no_lift_never_leaves_the_ground(self):
        self.assertIsNone(flight.runway_needed(-1.0, 0.1))

    def test_absurdly_long_runways_do_not_count(self):
        self.assertTrue(flight.flight_range(0.4, 0.05).can_fly)
        self.assertIsNone(flight.runway_needed(0.4, 0.05))

    def test_agrees_with_the_take_off_animation(self):
        for c_lift, c_drag in ((2.45, 0.16), (1.6, 0.3), (1.05, 0.2), (0.9, 0.1), (0.0003, 0.05)):
            run = flight.TakeoffRun(c_lift, c_drag)
            while not run.finished:
                run.tick()
            needed = flight.runway_needed(c_lift, c_drag)
            self.assertEqual(run.airborne, needed is not None and needed <= flight.RUNWAY_LENGTH)


class RunwayLength(unittest.TestCase):
    def test_ordinary_wing_takes_off(self):
        r = solve(5.0, 0.05, 0.12)
        self.assertLess(flight.runway_needed(r.c_lift_area, r.c_drag_area), flight.RUNWAY_LENGTH)

    def test_flat_wing_does_not_take_off(self):
        r = solve(0.0, 0.0, 0.12)
        self.assertIsNone(flight.runway_needed(r.c_lift_area, r.c_drag_area))


class CrashMessage(unittest.TestCase):
    def test_says_how_long_the_runway_needs_to_be(self):
        self.assertEqual(
            flight.crash_message(1.05, 0.2), "Runway too short, your wing needs a runway of 5,700 meters"
        )

    def test_no_message_if_no_runway_would_help(self):
        self.assertIsNone(flight.crash_message(0.00032337508, 0.04710259))
        self.assertIsNone(flight.crash_message(-1.0, 0.1))
        self.assertIsNone(flight.crash_message(0.4, 0.05))


class TakeoffMessage(unittest.TestCase):
    def test_says_where_the_plane_took_off(self):
        self.assertEqual(flight.takeoff_message(1817.56), "Take off in 1,818 meters")


class Takeoff(unittest.TestCase):
    def fly(self, c_lift, c_drag):
        run = flight.TakeoffRun(c_lift, c_drag)
        for _ in range(100000):
            run.tick()
            if run.finished:
                return run
        self.fail("Take-off never finished")

    def test_good_wing_takes_off(self):
        run = self.fly(2.4528644, 0.15818255)
        self.assertTrue(run.airborne)
        self.assertFalse(run.crash)

    def test_bad_wing_ends_in_the_sea(self):
        run = self.fly(0.00032337508, 0.04710259)
        self.assertFalse(run.airborne)
        self.assertTrue(run.touchdown)


class TimerTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("Needs a display")
        self.root.withdraw()
        self.timers = Timers(self.root)
        self.calls = []

    def tearDown(self):
        self.root.destroy()

    def test_timers_run_in_order(self):
        self.timers.after(60, lambda: self.calls.append("late"))
        self.timers.after(10, lambda: self.calls.append("early"))
        self.timers.after(100, self.root.quit)
        self.root.mainloop()
        self.assertEqual(self.calls, ["early", "late"])

    def test_cancelled_timer_does_not_run(self):
        timer = self.timers.after(10, lambda: self.calls.append("cancelled"))
        self.timers.cancel(timer)
        self.timers.after(50, self.root.quit)
        self.root.mainloop()
        self.assertEqual(self.calls, [])

    def test_exception_does_not_stop_the_event_loop(self):
        self.root.report_callback_exception = lambda *error: self.calls.append("reported")
        self.timers.after(10, lambda: 1 / 0)
        self.timers.after(50, self.root.quit)
        self.root.mainloop()
        self.assertEqual(self.calls, ["reported"])


class CpuLoad(unittest.TestCase):
    def test_reads_each_cpu_but_not_the_total(self):
        with tempfile.NamedTemporaryFile("w") as f:
            f.write("cpu  9 0 0 9 0 0 0 0 0 0\ncpu0 1 2 3 40 5 6 7 8 0 0\ncpu1 0 0 0 10 0 0 0 0 0 0\nintr 5\n")
            f.flush()
            self.assertEqual(cpu_window.read_cpu_times(f.name), {"cpu0": (27, 72), "cpu1": (0, 10)})

    def test_load_is_the_busy_fraction_since_the_last_reading(self):
        loads = cpu_window.cpu_loads({"cpu0": (10, 100), "cpu1": (0, 100)}, {"cpu0": (30, 120), "cpu1": (0, 120)})
        self.assertEqual(loads, {"cpu0": 1.0, "cpu1": 0.0})

    def test_no_time_passing_is_no_load(self):
        self.assertEqual(cpu_window.cpu_loads({"cpu0": (5, 9)}, {"cpu0": (5, 9)}), {"cpu0": 0.0})

    def test_this_machine_has_cpus(self):
        self.assertTrue(cpu_window.read_cpu_times())


class CpuWindowTests(unittest.TestCase):
    def test_window_closes_itself_after_the_solver_finishes(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Needs a display")
        self.addCleanup(root.destroy)
        closed = []
        window = cpu_window.CpuWindow(root, Timers(root), "8", lambda: (closed.append(True), root.quit()))
        window.timers.after(300, window.finish)
        root.mainloop()
        self.assertEqual(closed, [True])


class TakeoffWindowTests(unittest.TestCase):
    def test_reports_when_the_take_off_finishes(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Needs a display")
        self.addCleanup(root.destroy)
        finished = []
        window = takeoff_window.TakeoffWindow(
            root, Timers(root), 2.45, 0.16, lambda line: None, lambda: None, lambda: (finished.append(True), root.quit())
        )
        window.run.finished = True
        root.mainloop()
        self.assertEqual(finished, [True])


class RangeAnimation(unittest.TestCase):
    def animate(self, c_lift, c_drag):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Needs a display")
        self.addCleanup(root.destroy)
        root.withdraw()

        window = range_window.RangeWindow(root, Timers(root), c_lift, c_drag, lambda line: None, lambda: None)

        def wait_for_end():
            if window.next_frame is None:
                root.quit()
            else:
                window.timers.after(50, wait_for_end)

        wait_for_end()
        root.mainloop()
        return window

    def test_fuel_runs_out_when_the_plane_cannot_fly(self):
        window = self.animate(0.00032337508, 0.04710259)
        self.assertEqual(window.fuel, -range_window.FUEL_FULL)
        self.assertAlmostEqual(window.time_passed, flight.FULL_THROTTLE_HOURS, places=3)
        self.assertEqual(window.canvas.itemcget(window.clock, "text"), "03:28")

    def test_summary_explains_a_short_runway(self):
        summary = self.animate(1.05, 0.2).summary()
        self.assertIn("Runway too short", summary)
        self.assertIn(" m runway it could fly", summary)

    def test_summary_gives_no_figure_for_an_absurdly_long_runway(self):
        self.assertIn("far longer runway", self.animate(0.4, 0.05).summary())

    def test_summary_is_plain_when_the_plane_takes_off(self):
        self.assertNotIn("runway", self.animate(2.4528644, 0.15818255).summary())

    def test_summary_says_a_longer_runway_would_not_help(self):
        self.assertIn("even with a longer runway", self.animate(0.00032337508, 0.04710259).summary())

    def test_fuel_runs_out_when_the_plane_flies(self):
        window = self.animate(2.4528644, 0.15818255)
        self.assertEqual(window.fuel, -range_window.FUEL_FULL)
        self.assertAlmostEqual(window.time_passed, window.result.hours, places=3)


if __name__ == "__main__":
    unittest.main()
