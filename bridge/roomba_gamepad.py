#!/usr/bin/env python3
"""Drive the Roomba from a gamepad attached to the MQTT server.

Reads a Linux input device (Bluetooth-paired or USB-dongle controller) with evdev and
publishes the same MQTT messages as the web remote:

  roomba/drive     "<left>,<right>" wheel speeds in mm/s, repeated every 100 ms while held
  roomba/commands  drive_on / drive_off / start / stop / play_songN / vacuum_on / halt ...

Mapping: left stick drives, right trigger boosts, Start toggles drive mode, A clean,
B dock, X next song, Y vacuum toggle, Back/Select halt.
"""
import logging
import math
import os
import select
import time

log = logging.getLogger("roomba-gamepad")

BROKER = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USER = os.getenv("MQTT_USER", "")
PASSWORD = os.getenv("MQTT_PASS", "")
DEVICE = os.getenv("GAMEPAD_DEVICE", "")  # /dev/input/eventN or part of the device name
BASE_SPEED = int(os.getenv("BASE_SPEED", "250"))
MAX_WHEEL = 500
DEADZONE = float(os.getenv("DEADZONE", "0.12"))
TURN_GAIN = float(os.getenv("TURN_GAIN", "0.6"))
SEND_INTERVAL = 0.1
SONGS = ["play_song1", "play_song2", "play_song3", "play_song4", "play_song5"]


def mix(x, y, max_speed, deadzone=DEADZONE, turn_gain=TURN_GAIN):
    """Arcade-style mix of stick x/y (-1..1, y up positive) into (left, right) mm/s."""
    mag = math.hypot(x, y)
    if mag < deadzone:
        return 0, 0
    scale = min(1.0, (mag - deadzone) / (1 - deadzone)) / mag
    x, y = x * scale, y * scale
    left = y + x * turn_gain
    right = y - x * turn_gain
    m = max(1.0, abs(left), abs(right))
    max_speed = max(0, min(MAX_WHEEL, max_speed))
    return round(left / m * max_speed), round(right / m * max_speed)


def normalize(value, info):
    """Map a raw absolute-axis value to -1..1 (axes) using the device's absinfo."""
    span = info.max - info.min
    if span == 0:
        return 0.0
    return max(-1.0, min(1.0, (value - info.min) / span * 2 - 1))


def normalize_trigger(value, info):
    span = info.max - info.min
    return 0.0 if span == 0 else max(0.0, min(1.0, (value - info.min) / span))


class Bridge:
    def __init__(self, client):
        from evdev import ecodes

        self.ec = ecodes
        self.client = client
        self.drive_on = False
        self.vacuum_on = False
        self.song = 0
        self.x = self.y = self.boost = 0.0
        self.stop_repeats = 0
        self.buttons = {
            ecodes.BTN_START: self.toggle_drive,
            ecodes.BTN_SOUTH: lambda: self.command("start"),
            ecodes.BTN_EAST: lambda: self.command("stop"),
            ecodes.BTN_WEST: self.next_song,
            ecodes.BTN_NORTH: self.toggle_vacuum,
            ecodes.BTN_SELECT: lambda: self.command("halt"),
        }

    # MQTT
    def command(self, cmd):
        log.info("command %s", cmd)
        self.client.publish("roomba/commands", cmd)

    def on_message(self, _client, _userdata, msg):
        if msg.topic == "roomba/drive/state":
            self.drive_on = msg.payload.decode() == "on"
            if not self.drive_on:
                self.vacuum_on = False

    def toggle_drive(self):
        self.command("drive_off" if self.drive_on else "drive_on")

    def toggle_vacuum(self):
        if not self.drive_on:
            return
        self.vacuum_on = not self.vacuum_on
        self.command("vacuum_on" if self.vacuum_on else "vacuum_off")

    def next_song(self):
        self.command(SONGS[self.song])
        self.song = (self.song + 1) % len(SONGS)

    def send_drive(self):
        speed = BASE_SPEED + (MAX_WHEEL - BASE_SPEED) * self.boost
        left, right = mix(self.x, self.y, speed) if self.drive_on else (0, 0)
        if left or right:
            self.client.publish("roomba/drive", f"{left},{right}")
            self.stop_repeats = 3
        elif self.stop_repeats:
            self.client.publish("roomba/drive", "0,0")
            self.stop_repeats -= 1

    def stop(self):
        self.x = self.y = self.boost = 0.0
        for _ in range(3):
            self.client.publish("roomba/drive", "0,0")
        if self.drive_on:
            self.command("drive_off")

    # Gamepad
    def handle(self, dev, event):
        ec = self.ec
        if event.type == ec.EV_ABS:
            info = dev.absinfo(event.code)
            if event.code == ec.ABS_X:
                self.x = normalize(event.value, info)
            elif event.code == ec.ABS_Y:
                self.y = -normalize(event.value, info)
            elif event.code in (ec.ABS_RZ, ec.ABS_GAS):
                self.boost = normalize_trigger(event.value, info)
        elif event.type == ec.EV_KEY and event.value == 1:
            action = self.buttons.get(event.code)
            if action:
                action()

    def run_device(self, dev):
        log.info("using %s (%s)", dev.name, dev.path)
        next_send = time.monotonic()
        while True:
            timeout = max(0.0, next_send - time.monotonic())
            readable, _, _ = select.select([dev.fd], [], [], timeout)
            if readable:
                for event in dev.read():
                    self.handle(dev, event)
            if time.monotonic() >= next_send:
                self.send_drive()
                next_send = time.monotonic() + SEND_INTERVAL


def find_gamepad():
    from evdev import InputDevice, ecodes, list_devices

    for path in list_devices():
        dev = InputDevice(path)
        if DEVICE and DEVICE != dev.path and DEVICE not in dev.name:
            dev.close()
            continue
        caps = dev.capabilities()
        if ecodes.ABS_X in [c[0] if isinstance(c, tuple) else c for c in caps.get(ecodes.EV_ABS, [])] \
                and ecodes.BTN_SOUTH in caps.get(ecodes.EV_KEY, []):
            return dev
        dev.close()
    return None


def main():
    import paho.mqtt.client as mqtt

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="roomba-gamepad")
    if USER:
        client.username_pw_set(USER, PASSWORD)
    bridge = Bridge(client)
    client.on_message = bridge.on_message
    client.on_connect = lambda c, *_: c.subscribe("roomba/drive/state")
    client.connect_async(BROKER, PORT, keepalive=30)
    client.loop_start()

    while True:
        dev = find_gamepad()
        if dev is None:
            time.sleep(2)
            continue
        try:
            bridge.run_device(dev)
        except OSError as err:  # Controller turned off or out of range
            log.warning("controller lost: %s", err)
            bridge.stop()
        finally:
            dev.close()
        time.sleep(1)


if __name__ == "__main__":
    main()
