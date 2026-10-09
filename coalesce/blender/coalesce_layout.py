"""Where the small people stand, and where the camera looks from.

Pure Python (no bpy), shared by blender/build_coalesce.py and the tests.
Blender space: X right, Y depth (negative = toward the viewer), Z up.
Web space (layout.json, glTF): X right, Y up, Z toward the viewer; see to_web().
"""
import math
import random

TOKEN_SCALE = 0.40
GRID_DX = 0.265
GRID_DZ = 0.30
HEAD_Z, HEAD_R = 3.62, 1.2
SHOULDER_A, SHOULDER_B, SHOULDER_C = 2.45, 1.35, 2.35
ACCENT_RATE = 0.07
SEED = 7

CAMERA_TARGET = (0.35, 0.0, 2.45)
CAMERA_ELEVATION_DEG = 12.0
CAMERA_DISTANCE = 15.0
LENS_MM = 50.0
SENSOR_MM = 36.0
STILL_SIZE = (1400, 1080)

MAGNIFIER = {
    "lensRadius": 0.9,
    "rimOuter": 1.06,
    "standoff": 1.2,
    "handleAngleDeg": -52.0,
    "restAim": [0.95, 1.5],  # web x, y where the Help still (and the live lens) starts
}


def front_y(x, z):
    """Most-forward (most negative) Y of the head-and-shoulders volume at (x, z), or None outside it."""
    best = None
    q = HEAD_R ** 2 - x * x - (z - HEAD_Z) ** 2
    if q > 0:
        best = -math.sqrt(q)
    if z >= 0:
        q2 = 1 - (x / SHOULDER_A) ** 2 - (z / SHOULDER_C) ** 2
        if q2 > 0:
            y2 = -SHOULDER_B * math.sqrt(q2)
            best = y2 if best is None else min(best, y2)
    return best


def crowd_positions():
    """Base position of every person, packed on the figure's front surface, bottom row first."""
    positions = []
    for row in range(int(5.2 / GRID_DZ) + 1):
        z = row * GRID_DZ
        x = -3.0 + (GRID_DX / 2 if row % 2 else 0.0)
        while x <= 3.0 + 1e-9:
            y = front_y(x, z + 0.14)
            if y is not None and front_y(x, z + 0.27) is not None:
                positions.append((round(x, 4), round(y, 4), round(z, 4)))
            x += GRID_DX
    return positions


def accent_flags(count, rate=ACCENT_RATE, seed=SEED):
    rng = random.Random(seed)
    return [rng.random() < rate for _ in range(count)]


def camera_position():
    el = math.radians(CAMERA_ELEVATION_DEG)
    tx, ty, tz = CAMERA_TARGET
    return (tx, ty - CAMERA_DISTANCE * math.cos(el), tz + CAMERA_DISTANCE * math.sin(el))


def vertical_fov_deg():
    half_width = math.atan(SENSOR_MM / 2 / LENS_MM)
    aspect = STILL_SIZE[0] / STILL_SIZE[1]
    return math.degrees(2 * math.atan(math.tan(half_width) / aspect))


def to_web(point):
    x, y, z = point
    return [round(x, 4) + 0.0, round(z, 4) + 0.0, round(-y, 4) + 0.0]


def help_focus_index(positions):
    """Index of the person nearest the magnifier's resting aim (web x, y == Blender x, z)."""
    ax, ay = MAGNIFIER["restAim"]
    return min(range(len(positions)),
               key=lambda i: (positions[i][0] - ax) ** 2 + (positions[i][2] + 0.14 - ay) ** 2)


def layout_document(blender_version="unknown"):
    people = crowd_positions()
    zs = [p[2] for p in people]
    centre = (0.0, 0.0, round((min(zs) + max(zs)) / 2, 4))
    return {
        "version": 1,
        "generator": "blender/build_coalesce.py",
        "blender": blender_version,
        "tokenScale": TOKEN_SCALE,
        "people": [to_web(p) for p in people],
        "accent": [1 if flag else 0 for flag in accent_flags(len(people))],
        "figureCenter": to_web(centre),
        "camera": {
            "position": to_web(camera_position()),
            "target": to_web(CAMERA_TARGET),
            "vfovDeg": round(vertical_fov_deg(), 4),
            "aspect": round(STILL_SIZE[0] / STILL_SIZE[1], 4),
        },
        "magnifier": dict(MAGNIFIER),
    }
