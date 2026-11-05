"""Monte Carlo localization for a Roomba with only odometry, bumpers and light bumpers.

Each particle is a guess (x, y, theta) of where the robot is on the floor plan.
- Motion: every odometry step moves all particles by the measured travel plus some noise,
  because wheels slip.
- Walls: a particle whose robot outline would overlap a wall is almost certainly wrong.
- Bumps: when a bumper fires, particles that put a wall right where the bumper touched gain
  weight. Light bumpers do the same at a slightly longer reach.
Particles are then resampled in proportion to their weights, so the cloud collapses onto the
places that agree with everything the robot felt.
"""
import math

import numpy as np

from plan import ROBOT_RADIUS_MM, DistanceField

# Bearings of the sensors relative to straight ahead, radians (counter-clockwise positive)
BUMP_ANGLES = {1: math.radians(-40), 2: math.radians(40), 3: 0.0}   # bit0 right, bit1 left, both
LIGHT_ANGLES = [math.radians(a) for a in (65, 35, 12, -12, -35, -65)]  # bit0 left ... bit5 right
LIGHT_REACH_MM = ROBOT_RADIUS_MM + 60


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


class Localizer:
    def __init__(self, plan, particles=1500, rng=None):
        self.plan = plan
        self.field = DistanceField(plan)
        self.n = particles
        self.rng = rng or np.random.default_rng()
        self.x = np.zeros(self.n)
        self.y = np.zeros(self.n)
        self.th = np.zeros(self.n)
        self.w = np.full(self.n, 1.0 / self.n)
        self.since_light = 0.0
        self.spread_everywhere()

    # ---------- Initialisation ----------
    def spread_everywhere(self):
        """Unknown start: particles anywhere the robot could fit, any heading."""
        fx, fy = self.field.free_cells()
        if len(fx) == 0:
            raise ValueError("plan has no free space large enough for the robot")
        idx = self.rng.integers(0, len(fx), self.n)
        self.x = fx[idx] + self.rng.uniform(-self.field.res / 2, self.field.res / 2, self.n)
        self.y = fy[idx] + self.rng.uniform(-self.field.res / 2, self.field.res / 2, self.n)
        self.th = self.rng.uniform(-np.pi, np.pi, self.n)
        self.w[:] = 1.0 / self.n

    def set_pose(self, x, y, theta, sigma_xy=40.0, sigma_th=math.radians(2)):
        """Known start, e.g. sitting on the dock."""
        self.x = x + self.rng.normal(0, sigma_xy, self.n)
        self.y = y + self.rng.normal(0, sigma_xy, self.n)
        self.th = wrap(theta + self.rng.normal(0, sigma_th, self.n))
        self.w[:] = 1.0 / self.n

    # ---------- Updates ----------
    def move(self, distance, turn):
        """Apply one odometry step: distance (mm, forward positive) and turn (rad, CCW positive)."""
        if distance == 0 and turn == 0:
            return
        n = self.n
        # Noise per step: wheel slip scales distance a few percent; heading wanders slowly with
        # travel and more with turning (in-place spins slip the most)
        d = distance * (1 + self.rng.normal(0, 0.03, n)) + self.rng.normal(0, 1.0, n)
        t = turn * (1 + self.rng.normal(0, 0.15, n)) + self.rng.normal(0, 0.0005 + 0.00008 * abs(distance), n)
        mid = self.th + t / 2
        self.x += d * np.cos(mid)
        self.y += d * np.sin(mid)
        self.th = wrap(self.th + t)
        self.since_light += abs(distance)

        # The robot can't be inside a wall or outside every room
        clearance = self.field.lookup(self.x, self.y)
        inside = self.field.is_inside(self.x, self.y)
        self.w *= np.where(clearance < ROBOT_RADIUS_MM - 40, 0.1, 1.0)
        self.w *= np.where(inside, 1.0, 0.05)
        self._normalise()

    def bump(self, bits):
        """A bumper pressed: there is a wall where it touched (unless it hit unmapped furniture)."""
        angle = BUMP_ANGLES.get(bits & 3)
        if angle is None:
            return
        cx = self.x + ROBOT_RADIUS_MM * np.cos(self.th + angle)
        cy = self.y + ROBOT_RADIUS_MM * np.sin(self.th + angle)
        d = self.field.lookup(cx, cy)
        self.w *= 0.15 + 0.85 * np.exp(-(d ** 2) / (2 * 70.0 ** 2))
        self._normalise()

    def light(self, bits):
        """Light bumpers see something about 6 cm beyond the shell. Applied at most every 5 cm of travel."""
        if not bits or self.since_light < 50:
            return
        self.since_light = 0.0
        for i, angle in enumerate(LIGHT_ANGLES):
            if bits & (1 << i):
                cx = self.x + LIGHT_REACH_MM * np.cos(self.th + angle)
                cy = self.y + LIGHT_REACH_MM * np.sin(self.th + angle)
                d = self.field.lookup(cx, cy)
                self.w *= 0.35 + 0.65 * np.exp(-(d ** 2) / (2 * 90.0 ** 2))
        self._normalise()

    def _normalise(self):
        total = self.w.sum()
        if not np.isfinite(total) or total <= 1e-300:
            self.w[:] = 1.0 / self.n  # Everything disagreed: keep the cloud rather than divide by zero
        else:
            self.w /= total
        if 1.0 / np.sum(self.w ** 2) < self.n / 2:
            self._resample()

    def _resample(self):
        """Systematic resampling: keeps particles in proportion to their weight."""
        positions = (self.rng.random() + np.arange(self.n)) / self.n
        idx = np.searchsorted(np.cumsum(self.w), positions)
        idx = np.minimum(idx, self.n - 1)
        self.x, self.y, self.th = self.x[idx], self.y[idx], self.th[idx]
        self.w[:] = 1.0 / self.n
        # Re-seed a few particles anywhere, so a wrong guess can still recover (kidnapped robot)
        k = max(1, self.n // 200)
        fx, fy = self.field.free_cells()
        pick = self.rng.integers(0, len(fx), k)
        slots = self.rng.integers(0, self.n, k)
        self.x[slots], self.y[slots] = fx[pick], fy[pick]
        self.th[slots] = self.rng.uniform(-np.pi, np.pi, k)

    # ---------- Estimate ----------
    def estimate(self):
        x = float(np.sum(self.w * self.x))
        y = float(np.sum(self.w * self.y))
        th = float(math.atan2(np.sum(self.w * np.sin(self.th)), np.sum(self.w * np.cos(self.th))))
        # 80th-percentile distance from the estimate: ignores the few re-seeded particles
        dist = np.hypot(self.x - x, self.y - y)
        order = np.argsort(dist)
        cut = np.searchsorted(np.cumsum(self.w[order]), 0.8)
        spread = float(dist[order][min(cut, self.n - 1)])
        if spread < 250:
            confidence = "good"
        elif spread < 700:
            confidence = "rough"
        else:
            confidence = "lost"
        return {"x": round(x), "y": round(y), "th": round(th, 3), "spread": round(spread), "conf": confidence}
