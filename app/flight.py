"""Flight physics for the take-off animation and range map. No GUI code here."""
import math
import random
from collections import namedtuple

import numpy as np

# Location of the airport (degrees latitude and longitude)
LAT0 = 55.98
LON0 = -3.18

WING_LENGTH = 15.0  # m
MASS = 50.0  # tonnes
THRUST = 170.0  # kN
FUEL = 250.0  # units of fuel in the tank
MAX_FUEL_RATE = 0.02  # fuel used per second at maximum thrust
FULL_THROTTLE_HOURS = FUEL / MAX_FUEL_RATE / 3600  # how long a full tank lasts

EARTH_RADIUS = 6371.0  # km
RUNWAY_LENGTH = 4000.0  # m
RUNWAY_PIXELS = 700.0  # length of the runway in the take-off picture
WEIGHT = MASS * 10 * 1000.0  # N
RHO = 1.225  # air density (kg/m^3)
DT = 0.05  # simulated seconds per tick
SCALE = RUNWAY_PIXELS / RUNWAY_LENGTH  # metres to pixels
LONGEST_RUNWAY = 10000.0  # m, a wing needing more than this counts as never taking off

MAP_WIDTH = 1080
MAP_HEIGHT = 540
MAP_CENTRE_LON = -10.0  # longitude offset of the map image


class Raft:
    """A life raft that bobs away from the crashed plane."""

    def __init__(self, angle):
        self.x = 2.0 * math.cos(angle) * 25
        self.y = math.sin(angle) * 25
        self.dx = 2.0 * math.cos(angle)
        self.dy = math.sin(angle)

    def move(self):
        self.x += (self.dx + random.gauss(0.0, 5.0)) * 0.01
        self.y += (self.dy + random.gauss(0.0, 5.0)) * 0.01


class TakeoffRun:
    """State of one take-off attempt. Call tick() until finished is True."""

    def __init__(self, c_lift, c_drag, runway_length=RUNWAY_LENGTH):
        self.c_lift = c_lift
        self.c_drag = c_drag
        self.runway_length = runway_length

        self.x = 1000.0
        self.y = 345.0
        self.x0 = self.x
        self.vx = 0.0
        self.vy = 0.0
        self.t = 0.0

        self.altitude = 0.0
        self.climb_rate = 0.0  # variometer reading
        self.attitude_ticks = 0
        self.counter = 0
        self.waterlevel = 580.0

        self.crash = False
        self.airborne = False
        self.touchdown = False
        self.finished = False
        self.runway_used = None  # metres, set on lift-off

        self.rafts = [Raft(i * math.pi / 2.0 + math.pi / 4.0) for i in range(4)]
        self.splash_x = None

        # c_lift can be negative: fall back on a default so the marker still shows
        self.critical_speed = np.sqrt(
            WEIGHT / ((self.c_lift if self.c_lift > 0 else 2) * WING_LENGTH * 2 * 0.5 * RHO)
        )

        # Dial values: (altitude tens, altitude hundreds, speed, vertical speed)
        self.dials = (0.0, 0.0, 0.0, -125.0)

    def tick(self):
        if self.finished:
            return
        if not self.crash:
            self._roll()
        elif not self.touchdown:
            self._fall()
        else:
            self._sink()
        if self.altitude > 995 or self.vx > 355:
            self.finished = True

    def _roll(self):
        lift = self.c_lift * WING_LENGTH * 2 * 0.5 * RHO * self.vx * self.vx
        drag = self.c_drag * WING_LENGTH * 2 * 0.5 * RHO * self.vx * self.vx

        self.dials = (0.0, 0.0, self.vx, -125.0)

        self.vx = self.vx + (THRUST * 1000 - drag) * DT / (MASS * 1000)
        self.x = self.x - self.vx * DT * SCALE
        self.t = self.t + DT

        if lift > WEIGHT:
            self.y = self.y - 10.0 * DT

            previous = self.altitude
            self.altitude += 10.0 * DT / 0.35
            rate = (self.altitude - previous) * 100
            self.climb_rate = self.climb_rate + 10 if self.climb_rate <= rate - 10 else rate

            tens = self.altitude % 100
            self.dials = (tens, self.altitude - tens, self.vx, self.climb_rate - 125)
            self.attitude_ticks += 1

            if not self.airborne:
                self.y -= 10.0
                self.airborne = True
                self.runway_used = (self.x0 - self.x) / SCALE

        if (self.x0 - self.x) / SCALE > self.runway_length and not self.airborne:
            self.crash = True

    def _fall(self):
        self.vy = self.vy + 10 * DT
        self.y = self.y + self.vy * DT
        self.x = self.x - self.vx * DT * SCALE

        previous = self.altitude
        self.altitude -= 10.0 * DT / 0.35
        rate = (self.altitude - previous) * 100
        self.climb_rate = self.climb_rate - 5 if self.climb_rate >= rate + 5 else rate

        self.dials = (0.0, 0.0, self.vx, self.climb_rate - 125)

        if self.y > 500:
            self.y = 500
            self.touchdown = True
            self.splash_x = self.x - 10
            for raft in self.rafts:
                raft.x += self.x + 50.0
                raft.y += self.y + 30.0

    def _sink(self):
        self.counter += 1

        if self.counter > 50:
            for raft in self.rafts:
                raft.move()

        if self.counter > 100:
            self.vy = 0.5
            self.y = self.y + self.vy * DT
            self.waterlevel = self.waterlevel - 3.0 * self.vy * DT
            if self.waterlevel < 510:
                self.finished = True

    @property
    def warning_lights_on(self):
        return self.waterlevel >= 500 and self.counter % 50 < 25


def runway_needed(c_lift, c_drag):
    """Metres of runway needed to lift off, or None if no sensible runway is long enough."""
    run = TakeoffRun(c_lift, c_drag, runway_length=LONGEST_RUNWAY)
    while not (run.airborne or run.crash or run.finished):
        run.tick()
    return run.runway_used


RangeResult = namedtuple("RangeResult", "can_fly speed_kmph hours km")


def flight_range(c_lift, c_drag):
    """How far the plane can fly on a full tank with the given wing coefficients."""
    if c_lift <= 0.0:
        return RangeResult(False, 0.0, 0.0, 0.0)

    cruise = np.sqrt((2.0 * MASS * 1000 * 10) / (RHO * c_lift * 2 * WING_LENGTH))

    if cruise > np.sqrt((2.0 * THRUST * 1000) / (RHO * c_drag * 2 * WING_LENGTH)):
        return RangeResult(False, 0.0, 0.0, 0.0)

    cruise_thrust = 0.5 * RHO * cruise * cruise * c_drag * 2 * WING_LENGTH
    efficiency = cruise_thrust / 1000 / THRUST
    seconds = FUEL / (efficiency * MAX_FUEL_RATE)

    return RangeResult(True, cruise * 3.6, seconds / 3600, seconds * cruise / 1000)


def rounded_runway(metres):
    """A runway length rounded up to a tidy number."""
    return math.ceil(metres / 100) * 100


def crash_message(c_lift, c_drag):
    """What to tell a wing that ran out of runway, or None if no runway would help."""
    needed = runway_needed(c_lift, c_drag)
    if needed is None or not flight_range(c_lift, c_drag).can_fly:
        return None
    return f"Runway too short, your wing needs a runway of {rounded_runway(needed):,} meters"


def takeoff_message(metres):
    """What to tell a wing that lifted off after this much runway."""
    return f"Take off in {round(metres):,} meters"


def map_angles():
    """Angular distance (radians) from the airport to every pixel of the map."""
    step = 360.0 / MAP_WIDTH
    lon = np.radians(step * (np.arange(MAP_WIDTH) + 0.5) - 180.0 - MAP_CENTRE_LON)
    theta = np.radians(step * (np.arange(MAP_HEIGHT) - 0.5))

    phi0 = math.radians(LON0)
    theta0 = math.radians(90 - LAT0)
    x0 = math.sin(theta0) * math.cos(phi0)
    y0 = math.sin(theta0) * math.sin(phi0)
    z0 = math.cos(theta0)

    dot = (
        np.sin(theta)[:, None] * (np.cos(lon) * x0 + np.sin(lon) * y0)[None, :]
        + np.cos(theta)[:, None] * z0
    )
    return np.arccos(np.clip(dot, -1.0, 1.0))
