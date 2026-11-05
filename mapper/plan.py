"""Floor plan model shared by the importer and the mapper.

A plan is plain JSON in millimetres, map frame: x to the right, y up (as seen from above).

{
  "walls":     [[x1, y1, x2, y2], ...],          # solid wall segments (door openings already cut out)
  "doors":     [[x1, y1, x2, y2], ...],          # openings, drawn on the page but not obstacles
  "furniture": [{"type": "storage", "box": [[x, y], ...4 corners], "solid": true}, ...],
  "rooms":     [{"name": "Kitchen", "polygon": [[x, y], ...]}, ...],
  "dock":      {"x": 0, "y": 0, "theta_deg": 90}  # robot pose when sitting on the dock, facing out
}

Furniture marked "solid" (cabinets, appliances) is treated as an obstacle for localization;
tables, chairs, beds and sofas are not, because the robot drives under or between them.
"""
import json
import math

import numpy as np

ROBOT_RADIUS_MM = 170


def load(path):
    with open(path) as f:
        return normalize(json.load(f))


def save(plan, path):
    with open(path, "w") as f:
        json.dump(plan, f, indent=1)


def normalize(plan):
    plan = dict(plan)
    plan.setdefault("walls", [])
    plan.setdefault("doors", [])
    plan.setdefault("furniture", [])
    plan.setdefault("rooms", [])
    plan["walls"] = [[float(v) for v in w] for w in plan["walls"]]
    return plan


def obstacle_segments(plan):
    """Every segment the robot can bump into: walls plus the outline of solid furniture."""
    segs = [tuple(w) for w in plan["walls"]]
    for item in plan.get("furniture", []):
        if not item.get("solid"):
            continue
        box = item["box"]
        for i in range(len(box)):
            (x1, y1), (x2, y2) = box[i], box[(i + 1) % len(box)]
            segs.append((x1, y1, x2, y2))
    return np.array(segs, dtype=float).reshape(-1, 4)


def bounds(plan, margin=500.0):
    pts = []
    for x1, y1, x2, y2 in plan["walls"]:
        pts += [(x1, y1), (x2, y2)]
    for room in plan.get("rooms", []):
        pts += [tuple(p) for p in room["polygon"]]
    if not pts:
        raise ValueError("plan has no walls or rooms")
    a = np.array(pts)
    return a[:, 0].min() - margin, a[:, 1].min() - margin, a[:, 0].max() + margin, a[:, 1].max() + margin


def point_in_polygon(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def room_at(plan, x, y):
    for room in plan.get("rooms", []):
        if point_in_polygon(x, y, room["polygon"]):
            return room["name"]
    return None


def segment_distance(px, py, segs):
    """Distance from points (arrays px, py) to the nearest of segs (N x 4). Vectorised."""
    px = np.asarray(px, dtype=float)[..., None]
    py = np.asarray(py, dtype=float)[..., None]
    x1, y1, x2, y2 = segs[:, 0], segs[:, 1], segs[:, 2], segs[:, 3]
    dx, dy = x2 - x1, y2 - y1
    length2 = np.maximum(dx * dx + dy * dy, 1e-9)
    t = np.clip(((px - x1) * dx + (py - y1) * dy) / length2, 0, 1)
    cx, cy = x1 + t * dx, y1 + t * dy
    return np.sqrt((px - cx) ** 2 + (py - cy) ** 2).min(axis=-1)


class DistanceField:
    """Precomputed distance (mm) from every grid cell to the nearest obstacle segment."""

    def __init__(self, plan, resolution=25.0):
        self.res = resolution
        self.x0, self.y0, x1, y1 = bounds(plan)
        self.w = int(math.ceil((x1 - self.x0) / resolution)) + 1
        self.h = int(math.ceil((y1 - self.y0) / resolution)) + 1
        segs = obstacle_segments(plan)
        xs = self.x0 + np.arange(self.w) * resolution
        field = np.empty((self.h, self.w), dtype=np.float32)
        for row in range(self.h):  # Row by row keeps memory small on big plans
            y = self.y0 + row * resolution
            field[row] = segment_distance(xs, np.full_like(xs, y), segs)
        self.field = field
        self.inside = self._inside_mask(plan)

    def _inside_mask(self, plan):
        """True for cells inside any room polygon (where the robot can actually be)."""
        mask = np.zeros((self.h, self.w), dtype=bool)
        rooms = plan.get("rooms") or []
        if not rooms:
            return ~mask
        ys, xs = np.mgrid[0:self.h, 0:self.w]
        X = self.x0 + xs * self.res
        Y = self.y0 + ys * self.res
        for room in rooms:
            poly = room["polygon"]
            inside = np.zeros_like(mask)
            n = len(poly)
            for i in range(n):
                xa, ya = poly[i]
                xb, yb = poly[(i + 1) % n]
                if ya == yb:
                    continue
                crosses = (ya > Y) != (yb > Y)
                xint = (xb - xa) * (Y - ya) / (yb - ya) + xa
                inside ^= crosses & (X < xint)
            mask |= inside
        return mask

    def lookup(self, x, y):
        """Distance to the nearest obstacle; points off the grid count as far from walls but outside."""
        col = np.clip(((np.asarray(x) - self.x0) / self.res).astype(int), 0, self.w - 1)
        row = np.clip(((np.asarray(y) - self.y0) / self.res).astype(int), 0, self.h - 1)
        return self.field[row, col]

    def is_inside(self, x, y):
        col = ((np.asarray(x) - self.x0) / self.res).astype(int)
        row = ((np.asarray(y) - self.y0) / self.res).astype(int)
        ok = (col >= 0) & (col < self.w) & (row >= 0) & (row < self.h)
        out = np.zeros(np.shape(col), dtype=bool)
        out[ok] = self.inside[row[ok], col[ok]]
        return out

    def free_cells(self, clearance=ROBOT_RADIUS_MM):
        rows, cols = np.nonzero((self.field > clearance) & self.inside)
        return self.x0 + cols * self.res, self.y0 + rows * self.res
