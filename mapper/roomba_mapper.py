#!/usr/bin/env python3
"""Tracks where the Roomba is on your floor plan.

Listens:   roomba/odom, roomba/bump        odometry and bumps from the ESP8266
           roomba/charging, roomba/status  to snap to the dock when the robot is charging
           roomba/map/cmd                  "relocalize" (forget the position), "reload" (re-read the plan),
                                           "clear_obstacles", or {"cmd":"set_dock","x":..,"y":..} in plan mm
Publishes: roomba/map/plan        (retained) the floor plan, for the web remote to draw
           roomba/pose            {"x","y","th","conf","spread","room"} in plan millimetres
           roomba/room            (retained) name of the room the robot is in, for Home Assistant
           roomba/map/obstacles   (retained) bump points that are not on the plan (furniture, clutter)
"""
import json
import logging
import math
import os
import threading
import time

import paho.mqtt.client as mqtt

import plan as planlib
from localizer import ROBOT_RADIUS_MM, Localizer

log = logging.getLogger("roomba-mapper")

BROKER = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USER = os.getenv("MQTT_USER", "")
PASSWORD = os.getenv("MQTT_PASS", "")
DATA_DIR = os.getenv("DATA_DIR", "/data")
PLAN_PATH = os.getenv("PLAN_PATH", os.path.join(DATA_DIR, "plan.json"))
PARTICLES = int(os.getenv("PARTICLES", "1500"))
OBSTACLES_PATH = os.path.join(DATA_DIR, "obstacles.json")
# Odometry calibration: real movement / what the encoders reported. Wheels slip (most of all when
# spinning in place on carpet), so encoders over-count. The web remote's Calibrate sheet measures
# these and saves them to calibration.json; the env values are the starting point. Rough first
# measurement on the den floor 2026-11-05: 1 full spin read as ~543 degrees, ~1 m read as ~1.42 m.
CALIBRATION_PATH = os.path.join(DATA_DIR, "calibration.json")
DEFAULT_DIST_SCALE = float(os.getenv("ODOM_DIST_SCALE", "0.70"))
DEFAULT_TURN_SCALE = float(os.getenv("ODOM_TURN_SCALE", "0.66"))
CHARGING_STATES = {"1", "2", "3", "4"}  # Charging recovery, charging, trickle, waiting: on the dock


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class Mapper:
    def __init__(self, client):
        self.client = client
        self.lock = threading.Lock()
        self.prev_odom = None
        self.docked = False
        self.room = ""   # Not yet published, so the first pose always sets roomba/room
        self.obstacles = set()
        self.last_obstacle_publish = 0.0
        self.load_calibration()
        self.load_plan()
        self.load_obstacles()

    def load_calibration(self):
        self.dist_scale, self.turn_scale = DEFAULT_DIST_SCALE, DEFAULT_TURN_SCALE
        try:
            with open(CALIBRATION_PATH) as f:
                data = json.load(f)
            self.dist_scale = float(data.get("dist_scale", self.dist_scale))
            self.turn_scale = float(data.get("turn_scale", self.turn_scale))
        except (OSError, ValueError):
            pass
        log.info("odometry calibration: distance x%.3f, turn x%.3f", self.dist_scale, self.turn_scale)

    def save_calibration(self, dist_scale=None, turn_scale=None):
        if dist_scale:
            self.dist_scale = min(2.0, max(0.3, float(dist_scale)))
        if turn_scale:
            self.turn_scale = min(2.0, max(0.3, float(turn_scale)))
        with open(CALIBRATION_PATH, "w") as f:
            json.dump({"dist_scale": self.dist_scale, "turn_scale": self.turn_scale}, f)
        self.loc.reset_slip(spread=0.05)  # Measured values are close; let the filter fine-tune
        self.publish_calibration()
        log.info("calibration saved: distance x%.3f, turn x%.3f", self.dist_scale, self.turn_scale)

    def publish_calibration(self):
        self.client.publish("roomba/map/calibration", json.dumps(
            {"dist_scale": self.dist_scale, "turn_scale": self.turn_scale}), retain=True)

    # ---------- Plan and stored data ----------
    def load_plan(self):
        self.plan = planlib.load(PLAN_PATH)
        self.loc = Localizer(self.plan, particles=PARTICLES)
        log.info("plan loaded: %d walls, %d rooms", len(self.plan["walls"]), len(self.plan["rooms"]))
        if self.plan.get("dock"):
            self.snap_to_dock()

    def load_obstacles(self):
        try:
            with open(OBSTACLES_PATH) as f:
                self.obstacles = {tuple(p) for p in json.load(f)}
        except (OSError, ValueError):
            self.obstacles = set()

    def publish_plan(self):
        self.client.publish("roomba/map/plan", json.dumps(self.plan, separators=(",", ":")), retain=True)
        self.publish_obstacles(force=True)
        self.publish_calibration()

    def publish_obstacles(self, force=False):
        now = time.time()
        if not force and now - self.last_obstacle_publish < 10:
            return
        self.last_obstacle_publish = now
        points = sorted(self.obstacles)
        self.client.publish("roomba/map/obstacles", json.dumps(points, separators=(",", ":")), retain=True)
        try:
            with open(OBSTACLES_PATH, "w") as f:
                json.dump(points, f)
        except OSError as err:
            log.warning("could not save obstacles: %s", err)

    # ---------- Pose ----------
    def snap_to_dock(self):
        dock = self.plan.get("dock")
        if dock:
            self.loc.set_pose(dock["x"], dock["y"], math.radians(dock.get("theta_deg", 90)))  # Facing the dock
            log.info("snapped to dock")

    def publish_pose(self):
        est = self.loc.estimate()
        room = planlib.room_at(self.plan, est["x"], est["y"]) if est["conf"] != "lost" else None
        est["room"] = room
        self.client.publish("roomba/pose", json.dumps(est, separators=(",", ":")))
        if room != self.room:
            self.room = room
            self.client.publish("roomba/room", room or "Unknown", retain=True)

    # ---------- Message handlers ----------
    def apply_odometry(self, msg):
        """Turn the ESP's cumulative odometry into a step since the last message."""
        x, y, th = float(msg["x"]), float(msg["y"]), float(msg["th"])
        prev = self.prev_odom
        self.prev_odom = (x, y, th)
        if prev is None:
            return
        px, py, pth = prev
        dx, dy = x - px, y - py
        if math.hypot(dx, dy) > 1500:
            log.info("odometry jumped (ESP restart or odom_reset); skipping one step")
            return
        distance = (dx * math.cos(pth) + dy * math.sin(pth)) * self.dist_scale   # Signed: negative when reversing
        turn = wrap(th - pth) * self.turn_scale
        bits = int(msg.get("b", 0))
        if bits & 0x0C:
            return  # A wheel dropped: the robot is lifted or stuck, and spinning wheels count without moving it
        if bits & 0x03 and distance > 0:
            distance = 0.0  # Pushing into something with a bumper held: the wheels slip, the robot doesn't move
        if not self.docked:
            self.loc.move(distance, turn)

    def on_odom(self, msg):
        self.apply_odometry(msg)
        if not self.docked:
            self.loc.light(int(msg.get("lb", 0)))
        self.publish_pose()

    def on_bump(self, msg):
        self.apply_odometry(msg)
        bits = int(msg.get("b", 0))
        if self.docked or not bits & 3:
            return
        self.loc.bump(bits)
        est = self.loc.estimate()
        if est["conf"] == "good":
            self.record_obstacle(est, bits)
        self.publish_pose()

    def record_obstacle(self, est, bits):
        """A bump far from any mapped wall is probably furniture: remember it on a 10 cm grid."""
        angle = {1: -0.7, 2: 0.7, 3: 0.0}[bits & 3]
        cx = est["x"] + ROBOT_RADIUS_MM * math.cos(est["th"] + angle)
        cy = est["y"] + ROBOT_RADIUS_MM * math.sin(est["th"] + angle)
        if float(self.loc.field.lookup(cx, cy)) > 150:
            self.obstacles.add((round(cx / 100) * 100, round(cy / 100) * 100))
            self.publish_obstacles()

    def on_charging(self, value):
        docked = value in CHARGING_STATES
        if docked and not self.docked:
            self.snap_to_dock()
            self.publish_pose()
        self.docked = docked

    def set_dock(self, x, y, theta_deg=None):
        """Place the dock at (x, y). theta_deg is the robot's heading while docked: a Roomba docks
        head-first, so it faces the dock and the wall behind it. Without a heading, face the
        nearest wall, snapped to the plan's axes."""
        if theta_deg is None:
            angles = [i * math.pi / 36 for i in range(72)]
            near = [float(self.loc.field.lookup(x + 40 * math.cos(a), y + 40 * math.sin(a))) for a in angles]  # Steepest drop
            theta_deg = round(math.degrees(angles[near.index(min(near))]) / 90) * 90
        self.plan["dock"] = {"x": round(x), "y": round(y), "theta_deg": round(float(theta_deg)) % 360}
        planlib.save(self.plan, PLAN_PATH)
        log.info("dock set to %s", self.plan["dock"])
        self.publish_plan()
        if self.docked:
            self.snap_to_dock()

    def on_command(self, cmd):
        if cmd.startswith("{"):
            data = json.loads(cmd)
            if data.get("cmd") == "set_dock":
                self.set_dock(float(data["x"]), float(data["y"]), data.get("theta_deg"))
            elif data.get("cmd") == "set_calibration":
                self.save_calibration(data.get("dist_scale"), data.get("turn_scale"))
        elif cmd == "relocalize":
            self.loc.spread_everywhere()
        elif cmd == "reload":
            self.load_plan()
            self.publish_plan()
        elif cmd == "clear_obstacles":
            self.obstacles.clear()
            self.publish_obstacles(force=True)
        self.publish_pose()

    def on_message(self, _client, _userdata, message):
        payload = message.payload.decode(errors="replace")
        try:
            with self.lock:
                if message.topic == "roomba/odom":
                    self.on_odom(json.loads(payload))
                elif message.topic == "roomba/bump":
                    self.on_bump(json.loads(payload))
                elif message.topic == "roomba/charging":
                    self.on_charging(payload.strip())
                elif message.topic == "roomba/map/cmd":
                    self.on_command(payload.strip())
        except (ValueError, KeyError) as err:
            log.warning("bad %s message %r: %s", message.topic, payload[:80], err)


def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="roomba-mapper")
    if USER:
        client.username_pw_set(USER, PASSWORD)
    while not os.path.exists(PLAN_PATH):
        # Nothing to localize against yet: wait for import_plan.py to write the plan
        log.warning("no floor plan at %s yet; run import_plan.py (checking again every 30 s)", PLAN_PATH)
        time.sleep(30)
    mapper = Mapper(client)

    def on_connect(c, *_):
        c.subscribe([("roomba/odom", 0), ("roomba/bump", 0), ("roomba/charging", 0), ("roomba/map/cmd", 0)])
        mapper.publish_plan()
        mapper.publish_pose()
        log.info("connected to %s:%s", BROKER, PORT)

    client.on_connect = on_connect
    client.on_message = mapper.on_message
    client.connect_async(BROKER, PORT, keepalive=30)
    client.loop_start()
    # Heartbeat: keep the pose fresh for the web remote even while the robot sits still
    while True:
        time.sleep(5)
        if client.is_connected():
            with mapper.lock:
                mapper.publish_pose()


if __name__ == "__main__":
    main()
