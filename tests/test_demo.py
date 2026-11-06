"""Checks the solver and flight physics against results from the original demo.

Run from the repository root with: /usr/bin/python3 -s -m unittest discover tests
"""
import sys
import time
import tkinter as tk
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import flight
import simulation
from timers import Timers


def solve(*config):
    run = simulation.SolverRun(simulation.solver_config(*config))
    while not run.finished():
        time.sleep(0.05)
    return run.results()


class Solver(unittest.TestCase):
    def test_aerofoil(self):
        r = solve(simulation.AEROFOIL, 5.0, 0.05, 0.12)
        self.assertAlmostEqual(float(r.lift), 619.602417, places=2)
        self.assertAlmostEqual(float(r.drag), 36.7750778, places=3)
        self.assertAlmostEqual(float(r.c_lift), 0.638808906, places=5)

    def test_ellipse(self):
        r = solve(simulation.ELLIPSE, 15.0, 0.8, 0.3)
        self.assertEqual(r.speed.shape, (576, 576))
        self.assertGreater(float(r.lift), 0)


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


if __name__ == "__main__":
    unittest.main()
