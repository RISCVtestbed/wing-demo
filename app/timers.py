"""Timers that keep working if the system clock is changed.

Tk's own after() timers use the wall clock. If that steps backwards, for example
when NTP corrects it, every timer waits for the clock to catch up and the app
freezes. These timers count on a background thread using the monotonic clock,
which never goes backwards, then wake the Tk event loop through a pipe.
"""
import collections
import heapq
import itertools
import os
import sys
import threading
import time
import tkinter as tk


class Timers:
    def __init__(self, root):
        self.root = root
        self.ids = itertools.count(1)
        self.callbacks = {}  # timer id to callback, for timers not yet run
        self.waiting = []  # heap of (time due, timer id)
        self.due = collections.deque()  # timer ids ready to run on the Tk thread
        self.changed = threading.Condition()

        self.read_end, self.write_end = os.pipe()
        os.set_blocking(self.read_end, False)
        root.tk.createfilehandler(self.read_end, tk.READABLE, self.run_due)
        threading.Thread(target=self.count_down, daemon=True).start()

    def after(self, milliseconds, callback):
        """Call callback on the Tk thread after a delay. Returns an id for cancel()."""
        timer = next(self.ids)
        with self.changed:
            self.callbacks[timer] = callback
            heapq.heappush(self.waiting, (time.monotonic() + milliseconds / 1000, timer))
            self.changed.notify()
        return timer

    def cancel(self, timer):
        with self.changed:
            self.callbacks.pop(timer, None)

    def count_down(self):
        with self.changed:
            while True:
                if not self.waiting:
                    self.changed.wait()
                    continue
                delay = self.waiting[0][0] - time.monotonic()
                if delay > 0:
                    self.changed.wait(delay)
                    continue
                self.due.append(heapq.heappop(self.waiting)[1])
                os.write(self.write_end, b"x")

    def run_due(self, _file, _mask):
        os.read(self.read_end, 4096)
        while True:
            with self.changed:
                if not self.due:
                    return
                callback = self.callbacks.pop(self.due.popleft(), None)
            if callback is not None:
                try:
                    callback()
                except Exception:
                    # Left to escape, this would stop the Tk event loop
                    self.root.report_callback_exception(*sys.exc_info())
