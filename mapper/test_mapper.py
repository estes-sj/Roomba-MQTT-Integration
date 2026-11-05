"""Tests for the plan importer, the localizer and the mapper's message handling.

Run: python3 -m unittest -v test_mapper     (needs numpy; the USDZ test also needs usd-core)
"""
import json
import math
import os
import tempfile
import unittest

import numpy as np

import plan as planlib
from localizer import LIGHT_ANGLES, LIGHT_REACH_MM, ROBOT_RADIUS_MM, Localizer

# Two rooms: a 4 x 3 m living room and a 3 x 3 m kitchen east of it, with a 900 mm doorway
TWO_ROOMS = {
    "walls": [
        [0, 0, 7000, 0], [7000, 0, 7000, 3000], [7000, 3000, 0, 3000], [0, 3000, 0, 0],
        [4000, 0, 4000, 1000], [4000, 1900, 4000, 3000],
    ],
    "doors": [[4000, 1000, 4000, 1900]],
    "furniture": [{"type": "storage", "box": [[5800, 2400], [6900, 2400], [6900, 2900], [5800, 2900]], "solid": True}],
    "rooms": [
        {"name": "Living room", "polygon": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]]},
        {"name": "Kitchen", "polygon": [[4000, 0], [7000, 0], [7000, 3000], [4000, 3000]]},
    ],
    "dock": {"x": 300, "y": 1500, "theta_deg": 0},
}


def light_bits(field, x, y, th):
    bits = 0
    for i, a in enumerate(LIGHT_ANGLES):
        if field.lookup(x + LIGHT_REACH_MM * math.cos(th + a), y + LIGHT_REACH_MM * math.sin(th + a)) < 40:
            bits |= 1 << i
    return bits


def simulate(plan, steps, rng, drift=0.03):
    """Bounce around like a Roomba. Returns true poses plus what the ESP would report."""
    field = planlib.DistanceField(plan, resolution=10)
    x, y, th = plan["dock"]["x"], plan["dock"]["y"], math.radians(plan["dock"]["theta_deg"])
    events = []  # ("move", distance, turn) or ("bump", bits)
    truth = []
    for _ in range(steps):
        step = 20.0
        nx, ny = x + step * math.cos(th), y + step * math.sin(th)
        if field.lookup(nx, ny) < ROBOT_RADIUS_MM:
            # Which side touched: compare clearance a little to each side of the nose
            left = field.lookup(x + 180 * math.cos(th + 0.6), y + 180 * math.sin(th + 0.6))
            right = field.lookup(x + 180 * math.cos(th - 0.6), y + 180 * math.sin(th - 0.6))
            bits = 3 if abs(left - right) < 15 else (2 if left < right else 1)
            events.append(("bump", bits))
            turn = rng.uniform(1.6, 3.0) * (1 if bits == 1 else -1)
            # Back up 40 mm then turn; report the turn with a systematic gyro-free error
            x -= 40 * math.cos(th); y -= 40 * math.sin(th)
            events.append(("move", -40.0, 0.0))
            th += turn
            events.append(("move", 0.0, turn * (1 + drift)))
        else:
            x, y = nx, ny
            events.append(("move", step * (1 + drift / 2), 0.0, (x, y)))
            events.append(("light", light_bits(field, x, y, th)))
    return truth, events


class LocalizerTest(unittest.TestCase):
    def test_tracks_through_drift(self):
        rng = np.random.default_rng(3)
        plan = planlib.normalize(TWO_ROOMS)
        truth, events = simulate(plan, 2500, rng)
        loc = Localizer(plan, particles=1200, rng=np.random.default_rng(1))
        loc.set_pose(plan["dock"]["x"], plan["dock"]["y"], 0.0)
        dead = [plan["dock"]["x"], plan["dock"]["y"], 0.0]
        errors, dead_errors = [], []
        for ev in events:
            if ev[0] == "move":
                loc.move(ev[1], ev[2])
                dead[2] += ev[2]
                dead[0] += ev[1] * math.cos(dead[2]); dead[1] += ev[1] * math.sin(dead[2])
                if len(ev) == 4:  # Forward step carrying the true position after it
                    est = loc.estimate()
                    tx, ty = ev[3]
                    errors.append(math.hypot(est["x"] - tx, est["y"] - ty))
                    dead_errors.append(math.hypot(dead[0] - tx, dead[1] - ty))
            elif ev[0] == "light":
                loc.light(ev[1])
            else:
                loc.bump(ev[1])
        last = errors[-300:]
        print(f"\n  odometry-only error at end: {dead_errors[-1]:.0f} mm; "
              f"localizer median error (last 300 steps): {np.median(last):.0f} mm")
        self.assertGreater(dead_errors[-1], 500)
        self.assertLess(np.median(last), 300)

    def test_room_lookup(self):
        plan = planlib.normalize(TWO_ROOMS)
        self.assertEqual(planlib.room_at(plan, 1000, 1000), "Living room")
        self.assertEqual(planlib.room_at(plan, 5000, 1000), "Kitchen")
        self.assertIsNone(planlib.room_at(plan, 9000, 1000))


class ImportTest(unittest.TestCase):
    def test_door_cut_out_of_wall(self):
        from import_plan import cut_doors
        walls = cut_doors([[0, 0, 4000, 0]], [[1000, 20, 1900, 20]])
        self.assertEqual(walls, [[0, 0, 1000, 0], [1900, 0, 4000, 0]])

    def test_usdz_roomplan_like_scene(self):
        try:
            from pxr import Gf, Usd, UsdGeom, UsdUtils
        except ImportError:
            self.skipTest("usd-core not installed")
        tmp = tempfile.mkdtemp()
        usda = os.path.join(tmp, "room.usdc")
        stage = Usd.Stage.CreateNew(usda)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)

        def box(path, size, pos, yaw_deg=0):
            grp = UsdGeom.Xform.Define(stage, path + "_grp")
            grp.AddTranslateOp().Set(Gf.Vec3d(*pos))
            grp.AddRotateYOp().Set(yaw_deg)
            cube = UsdGeom.Cube.Define(stage, path + "_grp/" + path.split("/")[-1].replace("_", ""))
            cube.GetSizeAttr().Set(1.0)
            cube.AddScaleOp().Set(Gf.Vec3f(*size))

        UsdGeom.Xform.Define(stage, "/Room")
        # 4 m (x) by 3 m (z) room centred on the origin, walls 0.1 m thick, 2.4 m tall
        box("/Room/Wall_0", (4, 2.4, 0.1), (0, 1.2, -1.5))
        box("/Room/Wall_1", (4, 2.4, 0.1), (0, 1.2, 1.5))
        box("/Room/Wall_2", (3, 2.4, 0.1), (-2, 1.2, 0), yaw_deg=90)
        box("/Room/Wall_3", (3, 2.4, 0.1), (2, 1.2, 0), yaw_deg=90)
        box("/Room/Door_0", (0.9, 2.0, 0.1), (0.5, 1.0, 1.5))          # in the +z wall
        box("/Room/Storage_0", (1.2, 0.9, 0.5), (-1.3, 0.45, -1.2))
        box("/Room/Table_0", (1.0, 0.75, 0.6), (0.5, 0.375, 0))
        stage.Save()
        usdz = os.path.join(tmp, "room.usdz")
        UsdUtils.CreateNewUsdzPackage(usda, usdz)

        from import_plan import import_usdz
        plan = import_usdz(usdz)
        self.assertEqual(len(plan["doors"]), 1)
        self.assertEqual(len(plan["walls"]), 5)   # Door splits one wall into two
        kinds = {f["type"]: f["solid"] for f in plan["furniture"]}
        self.assertEqual(kinds, {"storage": True, "table": False})
        # +z wall is at plan y = -1500 (looking down, +z points toward the viewer's bottom)
        ys = sorted(round((w[1] + w[3]) / 2) for w in plan["walls"] if abs(w[1] - w[3]) < 5)
        self.assertEqual(ys[0], -1500)
        self.assertEqual(ys[-1], 1500)


class StubClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, retain=False):
        self.published.append((topic, payload, retain))


class MapperTest(unittest.TestCase):
    def test_messages(self):
        tmp = tempfile.mkdtemp()
        os.environ["DATA_DIR"] = tmp
        os.environ["PLAN_PATH"] = os.path.join(tmp, "plan.json")
        planlib.save(TWO_ROOMS, os.environ["PLAN_PATH"])
        import importlib
        import roomba_mapper
        importlib.reload(roomba_mapper)
        client = StubClient()
        m = roomba_mapper.Mapper(client)
        m.publish_plan()
        m.on_charging("2")                                # docked: snaps to the dock
        m.on_charging("0")                                # leaves the dock
        for i in range(0, 60):                            # drive 1.2 m forward (+x on the plan)
            m.on_odom({"x": i * 20, "y": 0, "th": 0, "lb": 0})
        pose = json.loads([p for t, p, _ in client.published if t == "roomba/pose"][-1])
        self.assertAlmostEqual(pose["x"], 300 + 1180, delta=150)
        self.assertEqual(pose["room"], "Living room")
        rooms = [p for t, p, r in client.published if t == "roomba/room" and r]
        self.assertEqual(rooms[-1], "Living room")
        self.assertTrue(any(t == "roomba/map/plan" and r for t, _, r in client.published))
        m.on_command('{"cmd":"set_dock","x":6800,"y":1500}')   # against the east wall
        self.assertEqual(planlib.load(os.environ["PLAN_PATH"])["dock"]["theta_deg"], 180)


if __name__ == "__main__":
    unittest.main()
