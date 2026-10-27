"""
One Euro Filter Implementation for GestureStrike.
Based on the paper:
Casiez, G., Roussel, N. and Vogel, D. (2012).
1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input in HCI.
Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (CHI '12).

Provides low-jitter at low speeds and zero lag at high speeds by dynamically
adapting the cutoff frequency based on the input signal's velocity.
"""

import math
import time


class LowPassFilter:
    """Standard first-order exponential low-pass filter."""

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.hat_x_prev = None

    def reset(self):
        self.hat_x_prev = None

    def filter(self, x: float, alpha: float = None) -> float:
        if alpha is not None:
            self.alpha = alpha
        if self.hat_x_prev is None:
            self.hat_x_prev = x
            return x
        hat_x = self.alpha * x + (1.0 - self.alpha) * self.hat_x_prev
        self.hat_x_prev = hat_x
        return hat_x


class OneEuroFilter:
    """
    1€ Filter that eliminates jitter when holding still while maintaining
    immediate responsiveness without latency when moving fast.
    """

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.05, d_cutoff: float = 1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.last_time = None
        self.last_x = None

    def reset(self):
        """Resets filter state."""
        self.x_filter.reset()
        self.dx_filter.reset()
        self.last_time = None
        self.last_x = None

    def set_parameters(self, min_cutoff: float = None, beta: float = None, d_cutoff: float = None):
        """Updates filter tuning parameters live."""
        if min_cutoff is not None:
            self.min_cutoff = max(0.05, float(min_cutoff))
        if beta is not None:
            self.beta = max(0.0, float(beta))
        if d_cutoff is not None:
            self.d_cutoff = max(0.1, float(d_cutoff))

    def _alpha(self, cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x: float, timestamp: float = None) -> float:
        """Filters input value x given current timestamp."""
        if timestamp is None:
            timestamp = time.time()

        if self.last_time is None:
            self.last_time = timestamp
            self.last_x = x
            return self.x_filter.filter(x, 1.0)

        dt = timestamp - self.last_time
        self.last_time = timestamp
        if dt <= 0.0:
            dt = 1e-4

        # 1. Estimate speed of motion (derivative)
        dx = (x - self.last_x) / dt
        self.last_x = x
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = self.dx_filter.filter(dx, a_d)

        # 2. Adapt cutoff frequency based on velocity
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, dt)

        # 3. Filter position with adapted cutoff
        return self.x_filter.filter(x, a)
