# Mapping and Localization

How modern Roombas know where they are, what an older Roomba (600/800 series) can and can't do, and how this project adds floor-plan positioning to one using wheel odometry, bumpers, and a floor plan scanned with an iPhone.

- [How modern Roombas navigate](#how-modern-roombas-navigate)
- [What an older Roomba can sense](#what-an-older-roomba-can-sense)
- [How this project does it](#how-this-project-does-it)
- [Setup](#setup)
- [The plan file](#the-plan-file)
- [MQTT topics](#mqtt-topics)
- [Tuning and limitations](#tuning-and-limitations)
- [Ideas for later](#ideas-for-later)

## How modern Roombas navigate

iRobot calls its navigation stack **iAdapt**, and it has gone through a few generations:

| Generation | Models (roughly) | How it works |
|---|---|---|
| iAdapt 1.0 | 400–800 series (including the 650 and 860) | No map. A set of reactive behaviours: spiral, wall-follow, bounce off obstacles, plus a timer and a "dirt detect" sensor. Coverage comes from repetition, not planning. |
| iAdapt 2.0 | 900 series (980, 960) | **vSLAM**: an upward-tilted camera recognises landmarks on walls and ceilings, while an optical floor sensor (like a mouse sensor) measures motion. The robot builds a map as it cleans and cleans in neat rows. |
| iAdapt 3.0 + Imprint Smart Maps | i-series, s9, j-series | Same camera-based vSLAM, but the map is kept between runs, so the app can show rooms, keep-out zones, and "clean the kitchen". The j-series adds a front camera for obstacle avoidance (cords, socks, pet waste), and the s9 adds a 3D depth sensor at the front. |
| ClearView LiDAR | 2025 lineup | A spinning laser rangefinder (LiDAR) measures distances to walls all around the robot, several times a second. This is what most other brands have used for years: maps are fast and accurate and work in the dark. |

All of these do the same two jobs at once, known as **SLAM** (Simultaneous Localization And Mapping):

1. **Odometry**: estimate how far the robot moved from wheel encoders, an optical floor sensor, and a gyro. On its own this always drifts, because wheels slip, carpets compress, and small heading errors grow into large position errors.
2. **Correction**: compare what the robot senses (camera landmarks or LiDAR distances) with the map, and pull the estimate back into line.

The map is what makes room names, zones, "clean this room", and per-room history possible.

## What an older Roomba can sense

The 600/800 series has no camera, LiDAR, or gyro. Over the serial port (iRobot's Open Interface, or OI, which is the port the ESP8266 already uses) it still reports a lot:

| Sensor | OI packet | What it tells us |
|---|---|---|
| Wheel encoders | 43, 44 | Raw encoder counts per wheel, about 508.8 per wheel turn (72 mm wheel, so 0.44 mm per count). This is the basis of odometry. |
| Requested wheel speeds | 41, 42 | What the robot is asking the wheels to do, including during its own cleaning cycles. Used to work out which way the wheels turn (see below). |
| Bumpers and wheel drops | 7 | Left/right bumper contact and wheel drop. A bump means "there is something right here". |
| Light bumpers | 45–51 (700/800 series and later 600s) | Six infrared sensors across the front that see a wall or obstacle a few centimetres before touching it. The 860 has them. |
| Cliff sensors | 9–12, 28–31 | Stairs and drops. Not used for mapping yet. |
| Battery and charging | 21, 25, 26 | Charge, capacity, and charging state. Charging means "on the dock", which is a known position. |

**Quirk:** on some models the encoder counts only ever go up, whichever way the wheel turns. The firmware therefore takes the direction from the requested wheel speed (packets 41/42) when the two disagree.

Odometry from encoders alone is surprisingly good over a metre or two and useless over a whole cleaning run. In this project's simulation of a bouncing Roomba, pure odometry was 1.3 m off after about 50 m of driving.

## How this project does it

The approach is to measure the map with a phone, and have the robot only work out where it is on that map. A Roomba can't build an accurate map with touch sensors, but it can localize on a known map, which is a much easier problem.

```
iPhone (RoomPlan LiDAR scan) ──usdz──> import_plan.py ──> plan.json
                                                              │
Roomba ─OI stream─> ESP8266 ─roomba/odom, roomba/bump─> roomba-mapper ─roomba/pose, roomba/room─> web remote, Home Assistant
```

### 1. Odometry on the ESP8266

The firmware asks the Roomba to **stream** sensor packets (OI opcode 148), so the Roomba pushes a frame every 15 ms instead of being polled. Each frame is checksum-verified and then:

- the change in each wheel's encoder count becomes distance travelled per wheel;
- the average of the two wheels is forward motion, and the difference divided by the wheel base (235 mm) is the turn;
- these accumulate into a pose `x, y, θ` in the **odometry frame** (x forward and y left of where the robot started, θ counter-clockwise).

The ESP publishes the pose on `roomba/odom` (5 times a second while moving) and publishes every bumper press immediately on `roomba/bump`. Battery and charging values now come from the same stream, so there is no more polling.

### 2. Localization on the server (Monte Carlo localization)

`mapper/roomba_mapper.py` runs a **particle filter**. It keeps about 1,500 guesses ("particles") of where the robot might be on the floor plan:

1. **Move**: each odometry step moves every particle by the measured distance and turn, plus a little random noise sized to how much wheels really slip. The cloud slowly spreads out as uncertainty grows.
2. **Rule out the impossible**: particles that would put the robot inside a wall, or outside every room, lose most of their weight.
3. **Use what the robot felt**: on a bump, particles that put a wall exactly where the bumper touched gain weight; particles that put open floor there lose it. Light bumpers do the same at about 6 cm further out. The model allows for unmapped furniture, so a bump against a chair doesn't wreck the estimate.
4. **Resample**: the cloud is redrawn in proportion to the weights, so it collapses back onto the positions that agree with everything sensed so far. A few particles are re-seeded at random, so a wrong guess can still recover.

The published pose is the weighted average. Confidence comes from how tight the cloud is: `good` (80% of particles within 25 cm), `rough` (within 70 cm), or `lost`.

**Anchors:** when the robot is charging, it is on the dock, so the filter snaps to the dock's position. Every run that starts from the dock therefore starts with a known pose.

In the test simulation (two rooms, a bouncing robot, 3% turn error and light bumpers), the localizer's median error over the last stretch was about 9 cm while raw odometry had drifted 1.3 m.

### 3. Bumps become a furniture map

When the filter is confident and a bump happens more than 15 cm from any wall on the plan, the contact point is saved as an **obstacle**. These are usually furniture legs, bins, and clutter. They are published on `roomba/map/obstacles`, kept in `obstacles.json`, and drawn as orange dots on the plan.

### 4. The web remote

The drive area picks the best source automatically:

| Source available | What you see |
|---|---|
| Mapper running with a plan | **Plan** and **Drive** tabs appear. Plan: your floor plan, rooms labelled, the robot at its position (faded while still searching), a 2-minute trail drawn once the position is confident, discovered obstacles, and a joystick that starts where your thumb lands. Drive: the robot-centred view with a fixed joystick. **Dock**, **Relocate** and **Calibrate** buttons appear. |
| Odometry only | The follow view (robot centred) with a trail from the real encoders. |
| Neither (old firmware) | The original estimate from your stick input. |

## Setup

### 1. Scan with the iPhone 15 Pro

The 15 Pro has LiDAR, so any app built on Apple's **RoomPlan** works. Scan with the lights on and walk slowly along every wall; RoomPlan detects walls, doors, windows, openings, and furniture as boxes. Apps that export USDZ (check each App Store listing for current free-tier limits):

- [RoomTrace](https://apps.apple.com/ee/app/roomtrace/id6762636021): free, exports USDZ, DXF, and JSON, everything stays on the phone.
- [KIRI Engine](https://www.kiriengine.app/blog/iphone-lidar-room-scan-floor-plan): Room Scan is on the free plan and exports USDZ.
- [Room(Scan)](https://apps.apple.com/us/app/id6447059850) and [QuickRoom3D](https://apps.apple.com/th/app/quickroom3d/id6779574521) also export USDZ.

Scan each connected area in **one session** if the app supports multi-room capture. Separate scans have separate coordinate systems, and the importer can't align them.

### 2. Import

Copy the `.usdz` to the server and run the importer inside the mapper container:

```
docker cp scan.usdz roomba-mapper:/data/scan.usdz
docker exec roomba-mapper python import_plan.py /data/scan.usdz -o /data/plan.json --room-name "Living room"
```

It prints a summary (walls, doors, furniture, overall size) and writes `/data/plan.svg`, a preview with a 1 m grid. Check that the walls look right.

What the importer does:

- Each wall becomes a line segment through the middle of the wall.
- Doors and openings are cut out of the walls they sit in, so the robot can drive through.
- Cabinets, appliances, toilets, and tubs become **solid** furniture (obstacles). Tables, chairs, beds, and sofas don't, because the robot drives under or between them.
- If the plan has no rooms, one room is made from the outline of all the walls.

DXF from a CAD or floor-plan app also works: `import_plan.py floor.dxf -o /data/plan.json --units mm`.

### 3. Name the rooms (optional)

Edit `rooms` in `/data/plan.json` (see [The plan file](#the-plan-file)) using coordinates read off `plan.svg`. To re-import a newer scan without losing your rooms and dock, add `--keep /data/plan.json` (write to a new file first, then move it over). Then reload the plan without restarting:

```
mosquitto_pub -t roomba/map/cmd -m reload
```

### 4. Place the dock

On the web remote, tap **Dock**, press on the plan where the dock sits, and drag toward the direction the robot faces while charging. A Roomba docks head-first, so on the dock it faces the dock and the wall behind it. The heading snaps to 15° steps and starts pointed at the nearest wall. Lift your finger to save it to `plan.json`. From then on, every time the robot charges, its position and heading reset to the dock.

### 5. Calibrate wheel slip

Wheels slip, most of all when spinning in place on carpet, so the encoders over-count. On the first den test, one full spin read as 543° and about 1 m read as 1.42 m. Calibration is automatic: tap **Calibrate** with Drive on, clear about 1.5 m of floor, and put a strip of tape at the robot's front.

- **Forward / Back**: the robot drives what its current calibration believes is 1 m, slowing for the last 20%. Measure how far it really went and enter it in cm. Forward and reverse each get their own factor.
- **Spin**: the robot spins what it believes is exactly 2 full turns. Enter how many degrees past its starting direction it stopped (negative if short).

Each factor is real movement ÷ what the encoders counted at the end, so overshooting the target doesn't matter. Repeat a test until the answer comes out close to 100 cm or 0°. A bump, a wheel drop, or touching the stick stops the test. The mapper saves the factors to `calibration.json` and applies them to every odometry step, and the Drive view uses them too. On top of that, each particle carries its own small slip correction, so the filter keeps fine-tuning during a run (published as `slip` in `roomba/pose`).

### 6. Drive

Press **Clean** or drive it yourself. While the room label says "finding position", the position is still settling. If it is ever clearly wrong, tap **Relocate**: the mapper spreads its guesses over the whole plan and lets bumps narrow them down. Docking also fixes it.

## The plan file

All values are millimetres in the **map frame**: x to the right and y up, as seen from above.

```json
{
  "walls":     [[0, 0, 7000, 0], [7000, 0, 7000, 3000]],
  "doors":     [[4000, 1000, 4000, 1900]],
  "furniture": [{"type": "storage", "box": [[5800, 2400], [6900, 2400], [6900, 2900], [5800, 2900]], "solid": true}],
  "rooms":     [{"name": "Kitchen", "polygon": [[4000, 0], [7000, 0], [7000, 3000], [4000, 3000]]}],
  "dock":      {"x": 300, "y": 1500, "theta_deg": 0}
}
```

- `walls`, `doors`: segments `[x1, y1, x2, y2]`. Doors are drawn but are not obstacles.
- `furniture`: four-corner boxes. Set `"solid": true` for anything the robot can't go under.
- `rooms`: polygons in drawing order. The first polygon that contains the robot names the room.
- `dock`: where the robot sits when charging, with `theta_deg` the direction it faces (0 = +x, 90 = +y).

## MQTT topics

| Topic | From | Payload |
|---|---|---|
| `roomba/odom` | ESP8266 | `{"x","y","th","b","lb","ls":[6],"vl","vr"}`: odometry pose (mm, rad), bumper bits, light bumper bits and signals, requested wheel speeds |
| `roomba/bump` | ESP8266 | `{"x","y","th","b","lb"}` the moment a bumper or wheel drop goes from clear to pressed |
| `roomba/commands` `odom_reset` | you | Zero the ESP's odometry |
| `roomba/map/plan` | mapper (retained) | The plan JSON, for the web remote |
| `roomba/pose` | mapper | `{"x","y","th","conf","spread","room"}` in plan millimetres |
| `roomba/room` | mapper (retained) | Room name, or `Unknown` |
| `roomba/map/obstacles` | mapper (retained) | `[[x, y], ...]` bump points not on the plan |
| `roomba/map/calibration` | mapper (retained) | `{"dist_scale","dist_scale_back","turn_scale"}` odometry slip factors |
| `roomba/map/cmd` | you / web remote | `relocalize`, `reload`, `clear_obstacles`, `{"cmd":"set_dock","x":..,"y":..,"theta_deg":..}`, or `{"cmd":"set_calibration","dist_scale":..,"dist_scale_back":..,"turn_scale":..}` |

## Tuning and limitations

- **It knows where it is; it doesn't plan paths.** The Roomba still cleans with its own bounce behaviour. The mapper tracks and records but doesn't steer.
- **Long open floors are the hardest case.** With nothing to touch, the cloud spreads until the next wall or light-bumper reading. Rooms with furniture and walls nearby converge fastest.
- **Wheel slip** is the biggest error source. Run the calibration on the floor the robot uses most. Readings are ignored while a wheel is dropped (robot lifted or stuck), and forward counts are ignored while a bumper is held (pushing into something).
- **Mirror-image rooms** (two identical rectangles) can confuse a touch-only robot. The dock anchor usually breaks the tie.
- **Unmapped furniture** is tolerated (bumps are weighted, never trusted absolutely), but scanning with furniture in place gives the best results.
- **Firmware:** the light bumper packets (45–51) need a 700/800 series or a later 600. Older robots still work, with bumpers only.
- Settings: `PARTICLES` (default 1500) trades CPU for robustness; each update takes a few milliseconds on a home server.

## Ideas for later

- **Go to a room**: the mapper already knows the robot's position, so a planner on the map plus `roomba/drive` commands could send it to "Kitchen", then start Spot or Clean there.
- **Coverage history**: save the trail per run and show which rooms got cleaned, and how thoroughly.
- **Camera tag**: a printed ArUco marker on the lid, seen by a Home Assistant camera, gives an exact position whenever it's in view. That is a perfect extra correction for the filter.
- **LiDAR upgrade**: a Raspberry Pi Zero 2 W with a cheap LiDAR (a used LDS-01, YDLIDAR X2) running ROS 2 `slam_toolbox` would give real modern-Roomba maps. That is a bigger hardware project.
