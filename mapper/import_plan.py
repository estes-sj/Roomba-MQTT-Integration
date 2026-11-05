#!/usr/bin/env python3
"""Convert a phone room scan or a CAD drawing into the mapper's plan.json.

    python3 import_plan.py scan.usdz -o /data/plan.json            # iPhone RoomPlan export
    python3 import_plan.py floor.dxf -o /data/plan.json --units mm  # any CAD/floor-plan app
    python3 import_plan.py plan.json --preview plan.svg            # just draw an existing plan

USDZ: any app built on Apple's RoomPlan (LiDAR iPhones/iPads) exports walls, doors, windows,
openings and furniture as boxes. Walls become segments, doors and openings are cut out of the
walls so the robot can drive through them, and cabinets/appliances become solid furniture.

DXF: LINE and LWPOLYLINE/POLYLINE entities become walls; entities on a layer whose name
contains "door" or "opening" become doors.

Every run also writes an SVG preview with a 1 m grid, so you can read coordinates for the
dock and room outlines.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

import plan as planlib

# RoomPlan object categories that the robot can't drive under or through
SOLID_FURNITURE = {"storage", "refrigerator", "stove", "oven", "dishwasher", "washer", "dryer",
                   "washerdryer", "fireplace", "bathtub", "toilet", "sink"}
FURNITURE_WORDS = SOLID_FURNITURE | {"table", "chair", "bed", "sofa", "television", "stairs"}


# ---------- USDZ (RoomPlan) ----------
def classify(name):
    n = name.lower()
    if n.startswith("floor"):
        return "floor", None
    if "wall" in n:
        return "wall", None
    if "door" in n:
        return "door", None
    if "opening" in n:
        return "door", None   # Openings are passable, like doors
    if "window" in n:
        return "window", None
    for word in FURNITURE_WORDS:
        if word in n:
            return "furniture", word
    return None, None


def footprint(corners2d):
    """Oriented rectangle of 2D points: centre, unit long axis, half length, half width."""
    pts = np.asarray(corners2d)
    centre = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - centre)
    axis = vt[0]
    perp = np.array([-axis[1], axis[0]])
    along = (pts - centre) @ axis
    across = (pts - centre) @ perp
    mid_along = (along.max() + along.min()) / 2
    mid_across = (across.max() + across.min()) / 2
    centre = centre + axis * mid_along + perp * mid_across
    return centre, axis, (along.max() - along.min()) / 2, (across.max() - across.min()) / 2


def import_usdz(path):
    try:
        from pxr import Gf, Usd, UsdGeom
    except ImportError:
        sys.exit("USDZ import needs the usd-core package: pip install usd-core")
    stage = Usd.Stage.Open(path)
    scale = UsdGeom.GetStageMetersPerUnit(stage) * 1000.0  # to millimetres
    y_up = UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.y
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])

    def plan_xy(p):
        # Looking down from above: Y-up scenes map (X, -Z) to plan (x, y); Z-up scenes use (X, Y)
        return (p[0] * scale, -p[2] * scale) if y_up else (p[0] * scale, p[1] * scale)

    prims = list(stage.Traverse())
    # RoomPlan exports often hold the same room several times (Parametric_grp as boxes, Mesh_grp
    # and Model_grp as meshes). Use one copy, preferring the clean parametric boxes.
    candidates = prims
    for group in ("Parametric_grp", "Mesh_grp", "Model_grp"):
        sub = [p for p in prims if f"/{group}/" in str(p.GetPath())]
        if any(p.IsA(UsdGeom.Gprim) for p in sub):
            candidates = sub
            break
    # Room types from RoomPlan sections (iOS 17+), e.g. Section_grp/livingRoom0
    sections = [p.GetName() for p in prims if p.GetParent() and p.GetParent().GetName() == "Section_grp"]

    items = []
    floors = []
    for prim in candidates:
        if not prim.IsA(UsdGeom.Gprim):
            continue  # Only actual shapes; groups like Wall_5_grp also hold the door, Chair_grp all chairs
        kind, word = classify(prim.GetName())
        if kind is None:
            continue
        if kind == "floor":
            floors.append(floor_outline(prim, plan_xy, Usd, UsdGeom, cache, Gf))
            continue
        bbox = cache.ComputeWorldBound(prim)
        rng = bbox.GetRange()
        if rng.IsEmpty():
            continue
        m = bbox.GetMatrix()
        lo, hi = rng.GetMin(), rng.GetMax()
        corners = [m.Transform(Gf.Vec3d(x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        items.append((kind, word, [plan_xy(c) for c in corners]))

    walls, doors, furniture = [], [], []
    for kind, word, corners in items:
        centre, axis, half_len, half_wid = footprint(corners)
        a, b = centre - axis * half_len, centre + axis * half_len
        seg = [round(a[0]), round(a[1]), round(b[0]), round(b[1])]
        if kind == "wall":
            walls.append(seg)
        elif kind == "door":
            doors.append(seg)
        elif kind == "furniture":
            perp = np.array([-axis[1], axis[0]])
            box = [centre + axis * sa * half_len + perp * sb * half_wid for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            furniture.append({"type": word, "box": [[round(p[0]), round(p[1])] for p in box],
                              "solid": word in SOLID_FURNITURE})
    plan = {"walls": cut_doors(walls, doors), "doors": doors, "furniture": furniture, "rooms": []}
    outlines = [f for f in floors if f and len(f) >= 3]
    if len(outlines) <= 1:
        # One room: RoomPlan's floor polygon can skip alcoves, so outline the walls instead
        name = room_name(sections[0]) if sections else "Room"
        if walls:
            plan["rooms"] = [default_room({"walls": walls, "doors": doors}, name)]
    else:
        for i, outline in enumerate(outlines):
            name = room_name(sections[i]) if i < len(sections) else f"Room {i + 1}"
            plan["rooms"].append({"name": name, "polygon": outline})
    return plan


def floor_outline(prim, plan_xy, Usd, UsdGeom, cache, Gf):
    """The floor polygon: a single-face floor mesh lists the room's corners in order."""
    if prim.IsA(UsdGeom.Mesh):
        mesh = UsdGeom.Mesh(prim)
        points = mesh.GetPointsAttr().Get() or []
        counts = mesh.GetFaceVertexCountsAttr().Get() or []
        indices = mesh.GetFaceVertexIndicesAttr().Get() or []
        xf = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        world = [plan_xy(xf.Transform(Gf.Vec3d(*p))) for p in points]
        if len(counts) == 1 and len(indices) == counts[0]:
            ring = [world[i] for i in indices]
        else:
            ring = hull(world)
    else:
        bbox = cache.ComputeWorldBound(prim)
        lo, hi, m = bbox.GetRange().GetMin(), bbox.GetRange().GetMax(), bbox.GetMatrix()
        ring = hull([plan_xy(m.Transform(Gf.Vec3d(x, y, z))) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    out = []
    for x, y in ring:  # Drop repeated points
        p = [round(x), round(y)]
        if not out or math.dist(out[-1], p) > 10:
            out.append(p)
    return out


def room_name(section):
    """livingRoom0 -> Living room"""
    base = section.rstrip("0123456789")
    words = []
    for ch in base:
        if ch.isupper() and words:
            words.append(" ")
        words.append(ch.lower())
    text = "".join(words).strip()
    return text[:1].upper() + text[1:] if text else "Room"


# ---------- DXF ----------
def import_dxf(path, units_mm):
    try:
        import ezdxf
    except ImportError:
        sys.exit("DXF import needs the ezdxf package: pip install ezdxf")
    doc = ezdxf.readfile(path)
    walls, doors = [], []

    def add(layer, x1, y1, x2, y2):
        seg = [round(x1 * units_mm), round(y1 * units_mm), round(x2 * units_mm), round(y2 * units_mm)]
        (doors if ("door" in layer.lower() or "opening" in layer.lower()) else walls).append(seg)

    for e in doc.modelspace():
        layer = e.dxf.get("layer", "")
        if e.dxftype() == "LINE":
            add(layer, e.dxf.start.x, e.dxf.start.y, e.dxf.end.x, e.dxf.end.y)
        elif e.dxftype() in ("LWPOLYLINE", "POLYLINE"):
            pts = [(p[0], p[1]) for p in (e.get_points("xy") if e.dxftype() == "LWPOLYLINE" else [v.dxf.location for v in e.vertices])]
            if e.closed and pts:
                pts.append(pts[0])
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                add(layer, x1, y1, x2, y2)
    return {"walls": cut_doors(walls, doors), "doors": doors, "furniture": []}


# ---------- Geometry helpers ----------
def cut_doors(walls, doors, tolerance=150):
    """Remove the stretch of each wall that a door or opening overlaps."""
    result = []
    for wall in walls:
        pieces = [wall]
        for door in doors:
            next_pieces = []
            for w in pieces:
                next_pieces += subtract(w, door, tolerance)
            pieces = next_pieces
        result += [p for p in pieces if math.dist(p[:2], p[2:]) > 30]
    return result


def subtract(wall, door, tolerance):
    a, b = np.array(wall[:2], float), np.array(wall[2:], float)
    length = np.linalg.norm(b - a)
    if length < 1:
        return [wall]
    u = (b - a) / length
    n = np.array([-u[1], u[0]])
    d1, d2 = np.array(door[:2], float), np.array(door[2:], float)
    if abs((d1 - a) @ n) > tolerance or abs((d2 - a) @ n) > tolerance:
        return [wall]  # Door isn't on this wall's line
    t1, t2 = sorted(((d1 - a) @ u, (d2 - a) @ u))
    t1, t2 = max(t1, 0), min(t2, length)
    if t2 <= t1:
        return [wall]
    out = []
    if t1 > 0:
        p = a + u * t1
        out.append([round(a[0]), round(a[1]), round(p[0]), round(p[1])])
    if t2 < length:
        p = a + u * t2
        out.append([round(p[0]), round(p[1]), round(b[0]), round(b[1])])
    return out


def align_to_axes(plan):
    """Rotate the plan so its walls run horizontal and vertical (scans come out at any angle)."""
    total = 0j
    for x1, y1, x2, y2 in plan["walls"]:
        length = math.hypot(x2 - x1, y2 - y1)
        total += length * complex(math.cos(4 * math.atan2(y2 - y1, x2 - x1)), math.sin(4 * math.atan2(y2 - y1, x2 - x1)))
    if abs(total) < 1:
        return plan, 0.0
    angle = math.atan2(total.imag, total.real) / 4   # Dominant wall direction, modulo 90 degrees
    c, s = math.cos(-angle), math.sin(-angle)

    def rot(x, y):
        return [round(x * c - y * s), round(x * s + y * c)]

    plan["walls"] = [rot(a, b) + rot(c_, d) for a, b, c_, d in plan["walls"]]
    plan["doors"] = [rot(a, b) + rot(c_, d) for a, b, c_, d in plan["doors"]]
    for item in plan.get("furniture", []):
        item["box"] = [rot(x, y) for x, y in item["box"]]
    for room in plan.get("rooms", []):
        room["polygon"] = [rot(x, y) for x, y in room["polygon"]]
    return plan, math.degrees(angle)


def hull(points):
    pts = sorted(set(map(tuple, points)))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def default_room(plan, name):
    pts = []
    for x1, y1, x2, y2 in plan["walls"] + plan["doors"]:
        pts += [(x1, y1), (x2, y2)]
    return {"name": name, "polygon": [list(p) for p in hull(pts)]}


# ---------- Preview ----------
def write_svg(plan, path):
    x0, y0, x1, y1 = planlib.bounds(plan, margin=600)
    w, h = x1 - x0, y1 - y0
    k = 900 / max(w, h)
    def X(x): return (x - x0) * k
    def Y(y): return (y1 - y) * k
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w*k:.0f}" height="{h*k:.0f}" font-family="sans-serif" font-size="11">',
           f'<rect width="100%" height="100%" fill="#e4eee8"/>']
    gx = math.floor(x0 / 1000) * 1000
    while gx <= x1:
        out.append(f'<line x1="{X(gx):.1f}" y1="0" x2="{X(gx):.1f}" y2="{h*k:.0f}" stroke="#8597ab" stroke-width="0.5"/>'
                   f'<text x="{X(gx)+2:.1f}" y="12" fill="#4b6280">{gx/1000:g} m</text>')
        gx += 1000
    gy = math.floor(y0 / 1000) * 1000
    while gy <= y1:
        out.append(f'<line x1="0" y1="{Y(gy):.1f}" x2="{w*k:.0f}" y2="{Y(gy):.1f}" stroke="#8597ab" stroke-width="0.5"/>'
                   f'<text x="2" y="{Y(gy)-2:.1f}" fill="#4b6280">{gy/1000:g} m</text>')
        gy += 1000
    for room in plan.get("rooms", []):
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in room["polygon"])
        cx = sum(p[0] for p in room["polygon"]) / len(room["polygon"])
        cy = sum(p[1] for p in room["polygon"]) / len(room["polygon"])
        out.append(f'<polygon points="{pts}" fill="#142a45" fill-opacity="0.05" stroke="#142a45" stroke-dasharray="4 4"/>'
                   f'<text x="{X(cx):.1f}" y="{Y(cy):.1f}" text-anchor="middle" fill="#142a45" font-weight="bold">{room["name"]}</text>')
    for item in plan.get("furniture", []):
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in item["box"])
        out.append(f'<polygon points="{pts}" fill="{"#8597ab" if item.get("solid") else "none"}" stroke="#4b6280"/>')
    for x1_, y1_, x2_, y2_ in plan["walls"]:
        out.append(f'<line x1="{X(x1_):.1f}" y1="{Y(y1_):.1f}" x2="{X(x2_):.1f}" y2="{Y(y2_):.1f}" stroke="#142a45" stroke-width="5"/>')
    for x1_, y1_, x2_, y2_ in plan["doors"]:
        out.append(f'<line x1="{X(x1_):.1f}" y1="{Y(y1_):.1f}" x2="{X(x2_):.1f}" y2="{Y(y2_):.1f}" stroke="#ff5a1f" stroke-width="2" stroke-dasharray="3 3"/>')
    dock = plan.get("dock")
    if dock:
        out.append(f'<circle cx="{X(dock["x"]):.1f}" cy="{Y(dock["y"]):.1f}" r="{170*k:.1f}" fill="#ff5a1f"/>'
                   f'<text x="{X(dock["x"]):.1f}" y="{Y(dock["y"])-170*k-4:.1f}" text-anchor="middle" fill="#142a45">dock</text>')
    out.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help=".usdz (RoomPlan), .dxf, or an existing plan .json")
    ap.add_argument("-o", "--output", help="plan.json to write")
    ap.add_argument("--preview", help="SVG preview path (default: next to the output)")
    ap.add_argument("--units", default="mm", choices=["mm", "cm", "m", "in", "ft"], help="DXF drawing units")
    ap.add_argument("--room-name", default="Home", help="name for the default room outline")
    ap.add_argument("--keep", help="existing plan.json whose rooms and dock should be kept")
    ap.add_argument("--no-align", action="store_true", help="keep the scan's original rotation")
    args = ap.parse_args()

    ext = os.path.splitext(args.source)[1].lower()
    if ext in (".usdz", ".usda", ".usdc", ".usd"):
        plan = import_usdz(args.source)
    elif ext == ".dxf":
        plan = import_dxf(args.source, {"mm": 1, "cm": 10, "m": 1000, "in": 25.4, "ft": 304.8}[args.units])
    elif ext == ".json":
        plan = planlib.load(args.source)
    else:
        sys.exit(f"don't know how to import {ext} files")
    plan = planlib.normalize(plan)
    if ext != ".json" and not args.no_align:
        plan, turned = align_to_axes(plan)
        if abs(turned) > 0.5:
            print(f"rotated {-turned:.1f} degrees to line the walls up with the axes")

    if args.keep and os.path.exists(args.keep):
        old = planlib.load(args.keep)
        plan["rooms"] = old.get("rooms") or plan["rooms"]
        if old.get("dock"):
            plan["dock"] = old["dock"]
    if not plan["rooms"] and plan["walls"]:
        plan["rooms"] = [default_room(plan, args.room_name)]

    x0, y0, x1, y1 = planlib.bounds(plan, margin=0)
    print(f"{len(plan['walls'])} walls, {len(plan['doors'])} doors/openings, "
          f"{len(plan['furniture'])} furniture, {len(plan['rooms'])} rooms; "
          f"{(x1-x0)/1000:.1f} m x {(y1-y0)/1000:.1f} m")
    if args.output:
        planlib.save(plan, args.output)
        print("wrote", args.output)
    preview = args.preview or (os.path.splitext(args.output)[0] + ".svg" if args.output else None)
    if preview:
        write_svg(plan, preview)
        print("preview", preview)


if __name__ == "__main__":
    main()
