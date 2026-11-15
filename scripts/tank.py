"""Procedural M1A2T Abrams, built at 1:1 metres (scaled down at the end)."""
import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Euler
from utils import (add_box, add_cyl, add_ico, add_loft, rect_ring, tri_prism,
                   mesh_object, collection, srgb)

TAU = math.pi * 2


# ---------------------------------------------------------------- track path

def _stadium_path(x_front=3.28, x_rear=-3.28, z_center=0.39, radius=0.34,
                  z_bottom=0.05, samples_per_m=14.0):
    """Closed track loop (XZ) as a list of (pos, tangent)."""
    pts = []
    bottom = 0.05
    top = z_center + radius

    def line(p0, p1):
        d = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        n = max(2, int(d * samples_per_m))
        for i in range(n):
            t = i / n
            pts.append(((p0[0] + (p1[0] - p0[0]) * t,
                         p0[1] + (p1[1] - p0[1]) * t),
                        (p1[0] - p0[0], p1[1] - p0[1])))

    def arc(cx, cz, a0, a1, r):
        steps = max(6, int(abs(a1 - a0) * r * samples_per_m))
        for i in range(steps):
            t = i / steps
            a = a0 + (a1 - a0) * t
            da = (a1 - a0)
            p = (cx + math.cos(a) * r, cz + math.sin(a) * r)
            tang = (-math.sin(a) * da, math.cos(a) * da)
            pts.append((p, tang))

    line((x_front, bottom), (x_rear, bottom))
    arc(x_rear, z_center, -math.pi / 2, -3 * math.pi / 2, radius)
    line((x_rear, top), (x_front, top))
    arc(x_front, z_center, math.pi / 2, -math.pi / 2, radius)
    return pts


def _sample_path(pts, distance):
    total = 0.0
    seglens = []
    for i in range(len(pts)):
        p0 = Vector(pts[i][0])
        p1 = Vector(pts[(i + 1) % len(pts)][0])
        L = (p1 - p0).length
        seglens.append(L)
        total += L
    d = distance % total
    for i, L in enumerate(seglens):
        if d <= L:
            t = d / L
            p0, t0 = pts[i]
            p1, t1 = pts[(i + 1) % len(pts)]
            pos = Vector((p0[0] + (p1[0] - p0[0]) * t, 0.0,
                          p0[1] + (p1[1] - p0[1]) * t))
            tang = Vector((t0[0], 0.0, t0[1])).normalized()
            return pos, tang, total
        d -= L
    p, t = pts[0]
    return Vector((p[0], 0, p[1])), Vector((t[0], 0, t[1])).normalized(), total


def _append_box(verts, faces, M, sx, sy, sz, off=(0, 0, 0)):
    base = len(verts)
    ox, oy, oz = off
    corners = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
               (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    for c in corners:
        v = Vector((ox + c[0] * sx / 2, oy + c[1] * sy / 2, oz + c[2] * sz / 2))
        verts.append(tuple(M @ v))
    for f in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
              (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        faces.append(tuple(base + i for i in f))


def build_tracks(M, coll, track_centers=(-1.36, 1.36)):
    path = _stadium_path()
    _, _, total = _sample_path(path, 0)
    n_links = int(round(total / 0.177))
    step = total / n_links
    objs = []
    for side, cy in enumerate(track_centers):
        verts, faces = [], []
        for i in range(n_links):
            pos, tang, _ = _sample_path(path, (i + 0.5) * step)
            nrm = Vector((-tang.z, 0.0, tang.x)).normalized()
            if nrm.z > 0.5:
                nrm = -nrm  # keep local Z pointing outward from the loop
            # rebuild so local Z points radially outwards for bottom/top runs
            if pos.z < 0.2:
                nrm = Vector((0, 0, -1))
            elif pos.z > 0.6:
                nrm = Vector((0, 0, 1))
            xax = tang
            yax = Vector((0, 1, 0))
            zax = xax.cross(yax)  # right-handed
            # matrix columns: local X -> tangent, Y -> width, Z -> outward
            mat = Matrix((
                (tang.x, 0.0, nrm.x, pos.x),
                (0.0, 1.0, 0.0, cy),
                (tang.z, 0.0, nrm.z, pos.z),
                (0.0, 0.0, 0.0, 1.0),
            ))
            # plate
            _append_box(verts, faces, mat, 0.170, 0.635, 0.052)
            # outer rubber pad
            _append_box(verts, faces, mat, 0.128, 0.50, 0.022,
                        off=(0, 0, -0.037))
            # guide horn
            _append_box(verts, faces, mat, 0.055, 0.085, 0.075,
                        off=(0, 0, 0.060))
            # end connector
            _append_box(verts, faces, mat, 0.028, 0.60, 0.075,
                        off=(0.079, 0, 0.0))
        ob = mesh_object('Track_L' if side == 0 else 'Track_R', verts, faces,
                         M['track'], coll, smooth=False)
        objs.append(ob)
    return objs


# ---------------------------------------------------------------- running gear

def build_running_gear(M, coll, track_centers=(-1.36, 1.36)):
    objs = []
    wheel_x = [-2.58, -1.72, -0.86, 0.0, 0.86, 1.72, 2.58]
    for side, cy in enumerate(track_centers):
        for i, wx in enumerate(wheel_x):
            for dy in (-0.135, 0.135):
                y = cy + dy
                objs.append(add_cyl(f'tire_{side}_{i}_{dy}', (wx, y, 0.375),
                                    0.305, 0.155, M['rubber'], coll, axis='Y',
                                    segs=28, bevel=0.006))
                objs.append(add_cyl(f'rim_{side}_{i}_{dy}', (wx, y, 0.375),
                                    0.235, 0.17, M['camo'], coll, axis='Y',
                                    segs=24, bevel=0.004))
                objs.append(add_cyl(f'rimin_{side}_{i}_{dy}', (wx, y, 0.375),
                                    0.155, 0.185, M['metal_dark'], coll, axis='Y',
                                    segs=20))
                objs.append(add_cyl(f'hub_{side}_{i}_{dy}', (wx, y, 0.375),
                                    0.072, 0.21, M['metal'], coll, axis='Y',
                                    segs=14))
        # idler (front)
        idl = (3.24, cy, 0.40)
        objs.append(add_cyl(f'idler_{side}', idl, 0.305, 0.20, M['camo'], coll,
                            axis='Y', segs=32, bevel=0.008))
        objs.append(add_cyl(f'idlerm_{side}', idl, 0.215, 0.225,
                            M['metal_dark'], coll, axis='Y', segs=24))
        objs.append(add_cyl(f'idlerh_{side}', idl, 0.085, 0.25, M['metal'], coll,
                            axis='Y', segs=16))
        # drive sprocket (rear)
        spx, spz = -3.24, 0.40
        objs.append(add_cyl(f'sprocket_{side}', (spx, cy, spz), 0.30, 0.23,
                            M['metal_dark'], coll, axis='Y', segs=28,
                            bevel=0.008))
        objs.append(add_cyl(f'sprocketh_{side}', (spx, cy, spz), 0.11, 0.27,
                            M['metal'], coll, axis='Y', segs=18))
        for t in range(13):
            a = TAU * t / 13
            objs.append(add_box(f'sptooth_{side}_{t}',
                                (spx + math.cos(a) * 0.335, cy,
                                 spz + math.sin(a) * 0.335),
                                (0.115, 0.19, 0.085), M['metal_dark'], coll,
                                rot=(0, -a, 0), bevel=0.006))
        # return rollers
        for i, rx in enumerate((-2.2, 0.0, 2.2)):
            objs.append(add_cyl(f'roller_{side}_{i}', (rx, cy, 0.745),
                                0.105, 0.16, M['metal_dark'], coll,
                                axis='Y', segs=18))
            objs.append(add_cyl(f'rollerh_{side}_{i}', (rx, cy, 0.745),
                                0.045, 0.19, M['metal'], coll, axis='Y',
                                segs=12))
        # suspension arms
        for i, wx in enumerate(wheel_x):
            objs.append(add_cyl(f'arm_{side}_{i}', (wx - 0.12, cy, 0.52),
                                0.048, 0.42, M['metal_dark'], coll, axis='X',
                                segs=10, rot=(0, math.radians(18), 0)))
        # shock absorbers at both ends
        for wx in (wheel_x[0], wheel_x[-1]):
            objs.append(add_cyl(f'shock_{side}_{wx}', (wx, cy * 0.92, 0.62),
                                0.035, 0.40, M['metal'], coll, axis='Z',
                                segs=8, rot=(0, 0.25, 0)))
    return objs


# ---------------------------------------------------------------- hull

def build_hull(M, coll):
    objs = []
    rings = [
        (3.96, rect_ring(1.47, 1.03, 0.73, 0.10)),
        (3.82, rect_ring(1.60, 1.12, 0.67, 0.10)),
        (3.40, rect_ring(1.76, 1.30, 0.52, 0.12)),
        (2.60, rect_ring(1.83, 1.30, 0.455, 0.12)),
        (0.60, rect_ring(1.83, 1.30, 0.445, 0.12)),
        (-2.60, rect_ring(1.83, 1.30, 0.445, 0.12)),
        (-3.55, rect_ring(1.79, 1.28, 0.55, 0.12)),
        (-3.96, rect_ring(1.62, 1.08, 0.76, 0.10)),
    ]
    hull = add_loft('Hull', rings, M['camo'], coll, bevel=0.022, smooth=False)
    objs.append(hull)

    # lower-side armour strips between the running gear
    for sy in (-1, 1):
        objs.append(add_box(f'hull_lower_{sy}', (0.2, sy * 1.58, 0.55),
                            (6.2, 0.14, 0.30), M['camo'], coll, bevel=0.01))

    # engine deck raised plate
    objs.append(add_box('EngineDeck', (-2.66, 0, 1.315),
                        (2.25, 3.30, 0.07), M['camo'], coll, bevel=0.02))
    # grilles
    for k, (gx, gy, gw, gl) in enumerate([
            (-2.2, -0.95, 1.05, 1.05), (-2.2, 0.95, 1.05, 1.05),
            (-3.35, 0.0, 0.65, 2.55)]):
        objs.append(add_box(f'grille_frame_{k}', (gx, gy, 1.365),
                            (gw + 0.10, gl + 0.10, 0.045),
                            M['paint_dark'], coll, bevel=0.012))
        n = 9
        for i in range(n):
            if k == 2:
                objs.append(add_box(f'grille_{k}_{i}',
                                    (gx, gy - gl / 2 + gl * (i + .5) / n, 1.385),
                                    (gw * 0.86, gl / n * 0.62, 0.045),
                                    M['metal_dark'], coll, bevel=0.004))
            else:
                objs.append(add_box(f'grille_{k}_{i}',
                                    (gx - gw / 2 + gw * (i + .5) / n, gy, 1.385),
                                    (gw / n * 0.62, gl * 0.86, 0.045),
                                    M['metal_dark'], coll, bevel=0.004))

    # filler caps / hatches on the deck
    for fx, fy in [(-3.5, -1.1), (-3.5, 1.1), (-1.55, 1.15)]:
        objs.append(add_cyl('fuelcap', (fx, fy, 1.345), 0.13, 0.04,
                            M['paint_dark'], coll, segs=16, bevel=0.006))

    # rear plate detail
    objs.append(add_box('rear_grille', (-4.0, 0, 0.95),
                        (0.06, 2.2, 0.34), M['metal_dark'], coll, bevel=0.008))
    for i in range(7):
        objs.append(add_box(f'rearfin_{i}', (-4.04, -1.0 + i * 0.333, 0.95),
                            (0.03, 0.10, 0.28), M['metal'], coll))
    for sy in (-1, 1):
        objs.append(add_box(f'taillight_{sy}', (-4.02, sy * 1.42, 0.98),
                            (0.09, 0.30, 0.22), M['paint_dark'], coll,
                            bevel=0.01))
        objs.append(add_box(f'taillens_{sy}', (-4.07, sy * 1.42, 0.98),
                            (0.02, 0.22, 0.14), M['red'], coll))
        objs.append(add_box(f'rearhook_{sy}', (-4.02, sy * 1.05, 0.55),
                            (0.14, 0.16, 0.30), M['metal_dark'], coll,
                            bevel=0.01))
    objs.append(add_cyl('pintle', (-4.05, 0, 0.56), 0.10, 0.20,
                        M['metal_dark'], coll, axis='X', segs=12))

    # driver's hatch, periscopes
    objs.append(add_cyl('driver_hatch', (2.82, -0.48, 1.335), 0.34, 0.055,
                        M['camo'], coll, segs=28, bevel=0.012))
    objs.append(add_cyl('driver_hatch2', (2.82, -0.48, 1.37), 0.26, 0.035,
                        M['paint_dark'], coll, segs=24))
    for i, (px, py) in enumerate([(3.10, -0.72), (3.14, -0.48), (3.10, -0.24)]):
        objs.append(add_box(f'peri_{i}', (px, py, 1.375), (0.16, 0.14, 0.09),
                            M['paint_dark'], coll, bevel=0.008))
        objs.append(add_box(f'perig_{i}', (px + 0.02, py, 1.395),
                            (0.13, 0.10, 0.03), M['lens'], coll))
    # driver's hatch handle
    objs.append(add_box('drvhandle', (2.82, -0.48, 1.41),
                        (0.18, 0.035, 0.03), M['metal'], coll))

    # head lights + brush guards
    for sy in (-1, 1):
        objs.append(add_box(f'headlampbox_{sy}', (3.74, sy * 1.30, 1.08),
                            (0.26, 0.42, 0.28), M['paint_dark'], coll,
                            bevel=0.015))
        for dyy in (-0.11, 0.11):
            objs.append(add_cyl(f'headlamp_{sy}_{dyy}',
                                (3.885, sy * 1.30 + dyy, 1.08), 0.105, 0.06,
                                M['lamp'], coll, axis='X', segs=20,
                                bevel=0.008))
            objs.append(add_cyl(f'headlamp_rim_{sy}_{dyy}',
                                (3.87, sy * 1.30 + dyy, 1.08), 0.125, 0.05,
                                M['metal_dark'], coll, axis='X', segs=20))
        # guard bars
        for dyy in (-0.19, 0.0, 0.19):
            objs.append(add_box(f'guardv_{sy}_{dyy}',
                                (3.93, sy * 1.30 + dyy, 1.08),
                                (0.03, 0.03, 0.42), M['metal_dark'], coll))
        for dzz in (-0.17, 0.17):
            objs.append(add_box(f'guardh_{sy}_{dzz}',
                                (3.93, sy * 1.30, 1.08 + dzz),
                                (0.03, 0.44, 0.03), M['metal_dark'], coll))
        # small blackout lights
        objs.append(add_box(f'blackout_{sy}', (3.90, sy * 1.53, 0.93),
                            (0.03, 0.10, 0.08), M['paint_dark'], coll))

    # tow hooks
    for sy in (-1, 1):
        objs.append(add_box(f'towhook_{sy}', (3.98, sy * 0.95, 0.62),
                            (0.12, 0.16, 0.34), M['metal_dark'], coll,
                            bevel=0.01))
        objs.append(add_box(f'towhole_{sy}', (4.02, sy * 0.95, 0.66),
                            (0.06, 0.07, 0.12), M['black'], coll))

    # front fender flaps
    for sy in (-1, 1):
        objs.append(add_box(f'fender_{sy}', (3.22, sy * 1.44, 0.80),
                            (0.55, 0.62, 0.05), M['rubber'], coll,
                            rot=(0, math.radians(-14), 0)))
    # rear mud flaps
    for sy in (-1, 1):
        objs.append(add_box(f'rearflap_{sy}', (-3.75, sy * 1.43, 0.72),
                            (0.06, 0.60, 0.52), M['rubber'], coll))

    # side skirts (7 panels + front angled flap)
    panel_x = [-3.42, -2.50, -1.58, -0.66, 0.26, 1.18, 2.10]
    for sy in (-1, 1):
        for i, px in enumerate(panel_x):
            cx = px + 0.44
            objs.append(add_box(f'skirt_{sy}_{i}', (cx, sy * 1.745, 0.785),
                                (0.86, 0.055, 0.455), M['camo'], coll,
                                bevel=0.012))
            objs.append(add_box(f'skirtrib_{sy}_{i}', (cx, sy * 1.775, 0.985),
                                (0.80, 0.02, 0.04), M['paint_dark'], coll))
            for bx in (-0.32, 0.32):
                objs.append(add_cyl(f'skirtbolt_{sy}_{i}_{bx}',
                                    (cx + bx, sy * 1.782, 0.955), 0.022, 0.015,
                                    M['metal'], coll, axis='Y', segs=8))
            # dark seam between panels
            if i < len(panel_x) - 1:
                objs.append(add_box(f'skirtgap_{sy}_{i}',
                                    (px + 0.88, sy * 1.735, 0.785),
                                    (0.026, 0.065, 0.455), M['paint_dark'], coll))
        objs.append(add_box(f'skirtfront_{sy}', (2.94, sy * 1.745, 0.79),
                            (0.62, 0.06, 0.44), M['camo'], coll,
                            rot=(0, math.radians(-18), 0), bevel=0.012))
        objs.append(add_box(f'skirtrear_{sy}', (-3.62, sy * 1.745, 0.80),
                            (0.42, 0.06, 0.42), M['camo'], coll,
                            rot=(0, math.radians(16), 0), bevel=0.012))
        # stowage boxes and a tarp on the sponson sides
        objs.append(add_box(f'sponsonbox_{sy}', (1.55, sy * 1.845, 1.13),
                            (0.62, 0.10, 0.24), M['camo'], coll, bevel=0.012))
        objs.append(add_box(f'sponsonbox2_{sy}', (-1.20, sy * 1.845, 1.12),
                            (0.72, 0.12, 0.26), M['paint_dark'], coll,
                            bevel=0.015))
        objs.append(add_cyl(f'tarp_{sy}', (-2.25, sy * 1.86, 1.14),
                            0.09, 0.62, M['green_flag'], coll, axis='X',
                            segs=12, bevel=0.01))

    # grab handles / tie downs on the upper hull
    for sy in (-1, 1):
        for gx in (-2.0, 0.4, 2.4):
            objs.append(add_box(f'grab_{sy}_{gx}', (gx, sy * 1.85, 1.22),
                                (0.16, 0.035, 0.035), M['metal'], coll))
            objs.append(add_box(f'grableg_{sy}_{gx}a', (gx - 0.07, sy * 1.85, 1.245),
                                (0.03, 0.03, 0.09), M['metal'], coll))
            objs.append(add_box(f'grableg_{sy}_{gx}b', (gx + 0.07, sy * 1.85, 1.245),
                                (0.03, 0.03, 0.09), M['metal'], coll))
    # spare track link on the glacis
    for i in range(4):
        objs.append(add_box(f'glacis_link_{i}', (3.52 - i * 0.05, -0.7 + i * 0.0, 1.16),
                            (0.03, 0.5, 0.13), M['track'], coll,
                            rot=(0, math.radians(-52), 0)))
    # bow machine-gun plug / cover
    objs.append(add_box('bowcover', (3.86, 0.72, 1.05), (0.05, 0.22, 0.16),
                        M['paint_dark'], coll, bevel=0.01))
    return objs


# ---------------------------------------------------------------- turret

def _antiair_gun(M, coll, base, scale=1.0, kind='m2'):
    x, y, z = base
    objs = []
    objs.append(add_cyl('mg_pedestal', (x, y, z), 0.075, 0.25, M['metal_dark'],
                        coll, segs=14, bevel=0.006))
    objs.append(add_cyl('mg_ring', (x, y, z + 0.14), 0.22, 0.05, M['metal'], coll,
                        segs=18))
    if kind == 'm2':
        objs.append(add_box('m2_receiver', (x + 0.10, y, z + 0.32),
                            (0.55, 0.17, 0.17), M['metal_dark'], coll,
                            bevel=0.012))
        objs.append(add_cyl('m2_barrel', (x + 0.72, y, z + 0.34), 0.032, 0.95,
                            M['metal'], coll, axis='X', segs=12))
        objs.append(add_cyl('m2_jacket', (x + 0.56, y, z + 0.34), 0.048, 0.42,
                            M['metal_dark'], coll, axis='X', segs=14))
        objs.append(add_box('m2_ammobox', (x - 0.02, y - 0.18, z + 0.28),
                            (0.34, 0.20, 0.23), M['paint_dark'], coll,
                            bevel=0.012))
        objs.append(add_box('m2_grip', (x - 0.18, y, z + 0.33),
                            (0.10, 0.30, 0.05), M['metal_dark'], coll))
        objs.append(add_box('m2_shield', (x - 0.05, y, z + 0.24),
                            (0.05, 0.53, 0.32), M['paint_dark'], coll,
                            bevel=0.01))
    else:
        objs.append(add_box('m240_receiver', (x + 0.06, y, z + 0.16),
                            (0.40, 0.12, 0.14), M['metal_dark'], coll,
                            bevel=0.008))
        objs.append(add_cyl('m240_barrel', (x + 0.55, y, z + 0.17), 0.023, 0.72,
                            M['metal'], coll, axis='X', segs=10))
        objs.append(add_box('m240_ammo', (x - 0.18, y - 0.12, z + 0.02),
                            (0.22, 0.18, 0.16), M['green_flag'], coll,
                            bevel=0.01))
        objs.append(add_box('m240_ammocradle', (x - 0.18, y - 0.12, z + 0.005),
                            (0.28, 0.22, 0.05), M['metal_dark'], coll,
                            bevel=0.004))
        objs.append(add_box('m240_ammobracket', (x - 0.07, y - 0.08, z + 0.06),
                            (0.10, 0.08, 0.06), M['metal_dark'], coll,
                            bevel=0.004))
        objs.append(add_box('m240_grip', (x - 0.12, y, z + 0.17),
                            (0.08, 0.20, 0.04), M['metal_dark'], coll))
        # skate rail
        objs.append(add_cyl('mg_rail', (x - 0.25, y, z + 0.04), 0.022, 1.1,
                            M['metal'], coll, axis='X', segs=8))
    return objs


def build_turret(M, coll):
    objs = []
    rings = [
        (1.92, rect_ring(0.56, 1.92, 1.63, 0.06)),
        (1.66, rect_ring(1.00, 2.05, 1.46, 0.08)),
        (1.20, rect_ring(1.32, 2.14, 1.335, 0.10)),
        (0.40, rect_ring(1.42, 2.18, 1.325, 0.12)),
        (-1.20, rect_ring(1.45, 2.18, 1.34, 0.12)),
        (-1.86, rect_ring(1.38, 2.11, 1.45, 0.10)),
        (-2.06, rect_ring(1.20, 2.01, 1.58, 0.08)),
    ]
    turret = add_loft('Turret', rings, M['camo'], coll, bevel=0.018)
    objs.append(turret)

    # turret ring / base collar
    objs.append(add_cyl('turret_ring', (-0.10, 0, 1.345), 1.30, 0.10,
                        M['paint_dark'], coll, segs=48))

    # mantlet
    objs.append(add_box('mantlet', (2.02, 0, 1.79), (0.34, 0.78, 0.55),
                        M['camo'], coll, bevel=0.03))
    objs.append(add_box('mantlet_top', (1.94, 0, 2.02), (0.50, 0.70, 0.18),
                        M['camo'], coll, bevel=0.02))
    objs.append(add_cyl('gun_dustcover', (2.22, 0, 1.835), 0.155, 0.38,
                        M['paint_dark'], coll, axis='X', segs=20, r2=0.13))

    # main gun: one continuous thermal sleeve with a bore evacuator bulge
    objs.append(add_cyl('gun_base', (2.55, 0, 1.835), 0.115, 0.66,
                        M['paint_dark'], coll, axis='X', segs=24, r2=0.100))
    # continuous inner barrel; no constrictions at the sleeve seams
    objs.append(add_cyl('gun_core', (4.35, 0, 1.835), 0.064, 4.72,
                        M['metal_dark'], coll, axis='X', segs=22))
    objs.append(add_cyl('gun_sleeve1', (3.55, 0, 1.835), 0.100, 1.42,
                        M['paint_dark'], coll, axis='X', segs=24, r2=0.095))
    objs.append(add_cyl('gun_sleeve2', (4.75, 0, 1.835), 0.095, 1.10,
                        M['paint_dark'], coll, axis='X', segs=24, r2=0.090))
    objs.append(add_cyl('gun_evac', (4.62, 0, 1.835), 0.141, 0.52,
                        M['paint_dark'], coll, axis='X', segs=26, r2=0.141,
                        bevel=0.018))
    objs.append(add_cyl('gun_sleeve3', (5.90, 0, 1.835), 0.088, 1.32,
                        M['paint_dark'], coll, axis='X', segs=24, r2=0.080))
    objs.append(add_cyl('gun_muzzle', (6.55, 0, 1.835), 0.074, 0.32,
                        M['metal_dark'], coll, axis='X', segs=22, r2=0.082,
                        bevel=0.006))
    # bore is a dark disc, muzzle reference sensor
    objs.append(add_cyl('gun_bore', (6.705, 0, 1.835), 0.055, 0.02,
                        M['black'], coll, axis='X', segs=20))
    objs.append(add_box('mrs_mount', (6.28, 0.0, 1.96), (0.22, 0.10, 0.10),
                        M['metal_dark'], coll, bevel=0.01))
    objs.append(add_box('mrs', (6.34, 0.10, 1.99), (0.13, 0.06, 0.10),
                        M['metal'], coll, bevel=0.008))

    # CITV (commander's independent thermal viewer), right side of roof
    objs.append(add_cyl('citv_base', (-0.30, 0.82, 2.22), 0.27, 0.12,
                        M['camo'], coll, segs=22, bevel=0.01))
    objs.append(add_box('citv_body', (-0.30, 0.82, 2.38), (0.50, 0.46, 0.30),
                        M['camo'], coll, bevel=0.02))
    objs.append(add_cyl('citv_lens', (0.02, 0.82, 2.40), 0.165, 0.10,
                        M['paint_dark'], coll, axis='X', segs=24))
    objs.append(add_cyl('citv_glass', (0.075, 0.82, 2.40), 0.13, 0.02,
                        M['lens'], coll, axis='X', segs=24))
    objs.append(add_box('citv_top', (-0.30, 0.82, 2.55), (0.42, 0.40, 0.035),
                        M['paint_dark'], coll, bevel=0.01))
    for i in range(3):
        objs.append(add_box(f'citv_handle_{i}', (-0.45 + i * 0.15, 1.05, 2.50),
                            (0.12, 0.04, 0.035), M['metal'], coll))

    # GPS (gunner's primary sight), left front roof
    objs.append(add_box('gps_body', (0.94, -0.82, 2.31), (0.62, 0.52, 0.31),
                        M['camo'], coll, bevel=0.025))
    objs.append(add_box('gps_front', (1.27, -0.82, 2.30), (0.08, 0.44, 0.25),
                        M['paint_dark'], coll, bevel=0.012))
    objs.append(add_box('gps_glass', (1.32, -0.82, 2.31), (0.015, 0.34, 0.17),
                        M['lens'], coll))
    objs.append(add_box('gps_cover', (1.20, -0.82, 2.49), (0.30, 0.46, 0.045),
                        M['paint_dark'], coll, bevel=0.01))
    objs.append(add_box('gps_arm', (1.45, -0.82, 2.44), (0.24, 0.10, 0.06),
                        M['metal_dark'], coll))
    for sy in (-1, 1):
        objs.append(add_box(f'gps_side_{sy}', (0.94, -0.82 + sy * 0.29, 2.34),
                            (0.50, 0.06, 0.22), M['camo'], coll, bevel=0.01))
    objs.append(add_box('gps_topbox', (0.80, -0.82, 2.50), (0.22, 0.30, 0.09),
                        M['metal_dark'], coll, bevel=0.008))

    # commander's cupola + M2
    objs.append(add_cyl('cupola', (-0.52, 0.55, 2.27), 0.42, 0.22,
                        M['camo'], coll, segs=28, bevel=0.012))
    objs.append(add_cyl('cupola_ring', (-0.52, 0.55, 2.40), 0.40, 0.06,
                        M['paint_dark'], coll, segs=28))
    objs.append(add_cyl('cupola_hatch', (-0.52, 0.55, 2.45), 0.32, 0.045,
                        M['camo'], coll, segs=24, bevel=0.01))
    for i in range(6):
        a = TAU * i / 6
        px = -0.52 + math.cos(a) * 0.36
        py = 0.55 + math.sin(a) * 0.36
        objs.append(add_box(f'cupola_peri_{i}', (px, py, 2.31),
                            (0.14, 0.10, 0.13), M['paint_dark'], coll,
                            rot=(0, 0, a), bevel=0.006))
        objs.append(add_box(f'cupola_perig_{i}', (px, py, 2.335),
                            (0.11, 0.02, 0.07), M['lens'], coll,
                            rot=(0, 0, a)))
    objs += _antiair_gun(M, coll, (-0.45, 0.55, 2.38), kind='m2')

    # loader's hatch + M240
    objs.append(add_cyl('loader_hatch', (-0.18, -0.86, 2.20), 0.36, 0.06,
                        M['camo'], coll, segs=26, bevel=0.01))
    objs.append(add_cyl('loader_hatch2', (-0.18, -0.86, 2.235), 0.28, 0.035,
                        M['paint_dark'], coll, segs=22))
    objs += _antiair_gun(M, coll, (0.10, -1.02, 2.20), kind='m240')

    # antenna mounts and antennas with pennants
    for sy in (-1, 1):
        bx, by = -1.78, sy * 1.18
        objs.append(add_cyl(f'antbase_{sy}', (bx, by, 2.15), 0.075, 0.18,
                            M['metal_dark'], coll, segs=12, bevel=0.006))
        objs.append(add_cyl(f'ant_{sy}', (bx - 0.10, by + sy * 0.08, 3.35),
                            0.014, 2.42, M['metal'], coll, segs=8,
                            r2=0.004, rot=(math.radians(-4 * sy),
                                           math.radians(5), 0)))
        # yellow pennant near the top
        p = Vector((bx - 0.14, by + sy * 0.10, 4.10))
        verts = [tuple(p), tuple(p + Vector((0.26, 0, -0.055))),
                 tuple(p + Vector((0.0, 0.0, -0.20)))]
        objs.append(tri_prism(f'flag_{sy}', verts[0], verts[1], verts[2],
                              0.012, M['yellow'], coll, normal=(0, 1, 0)))

    # smoke grenade launchers, recessed into the sloped turret side
    for sy in (-1, 1):
        bx, bz = 1.18, 2.03
        objs.append(add_box(f'smoke_mount_{sy}', (bx, sy * 1.32, 2.00),
                            (0.60, 0.18, 0.30), M['paint_dark'], coll,
                            bevel=0.01))
        objs.append(add_box(f'smoke_base_{sy}', (bx, sy * 1.38, bz),
                            (0.55, 0.14, 0.22), M['camo'], coll,
                            bevel=0.012))
        for ix in (-0.14, 0.14):
            for iz in (-0.10, 0.10):
                objs.append(add_cyl(f'smoke_{sy}_{ix}_{iz}',
                                    (bx + ix, sy * 1.47, bz + iz),
                                    0.055, 0.34, M['paint_dark'], coll,
                                    axis='X', segs=12,
                                    rot=(0, math.radians(-24), 0),
                                    bevel=0.004))

    # ARAT-style ERA tiles on turret sides
    for sy in (-1, 1):
        for col in range(4):
            for row in range(2):
                ex = 0.55 - col * 0.49
                ez = 1.55 + row * 0.24
                objs.append(add_box(f'era_{sy}_{col}_{row}',
                                    (ex, sy * 1.465, ez),
                                    (0.44, 0.075, 0.215), M['camo'], coll,
                                    bevel=0.012))
        # side stowage box, recessed into the side with two mounting rails
        objs.append(add_box(f'sidebox_{sy}', (-1.35, sy * 1.40, 1.72),
                            (0.55, 0.12, 0.34), M['camo'], coll,
                            bevel=0.012))
        for rz in (1.63, 1.81):
            objs.append(add_box(f'sidebox_rail_{sy}_{rz}',
                                (-1.35, sy * 1.435, rz),
                                (0.56, 0.03, 0.035), M['paint_dark'], coll))
        # spare track links bolted to a shallow rail on the turret side
        objs.append(add_box(f'sparelink_rail_{sy}', (-1.12, sy * 1.435, 1.97),
                            (0.43, 0.02, 0.32), M['paint_dark'], coll))
        for k in range(3):
            objs.append(add_box(f'sparelink_{sy}_{k}',
                                (-0.95 - k * 0.17, sy * 1.44, 1.97),
                                (0.15, 0.035, 0.28), M['track'], coll,
                                bevel=0.005))
        # lifting eyes
        for lx in (0.9, -1.3):
            objs.append(add_box(f'lift_{sy}_{lx}', (lx, sy * 1.42, 2.19),
                                (0.16, 0.08, 0.09), M['metal'], coll,
                                bevel=0.008))
        # lifting eyes
        for lx in (0.9, -1.3):
            objs.append(add_box(f'lift_{sy}_{lx}', (lx, sy * 1.42, 2.19),
                                (0.16, 0.08, 0.09), M['metal'], coll,
                                bevel=0.008))

    # turret roof detail: wind sensor, hatches, grab rails
    objs.append(add_box('wind_sensor_plate', (-1.40, -0.42, 2.19),
                        (0.24, 0.20, 0.035), M['paint_dark'], coll,
                        bevel=0.006))
    objs.append(add_cyl('wind_sensor_base', (-1.40, -0.42, 2.205), 0.09, 0.06,
                        M['paint_dark'], coll, segs=14))
    objs.append(add_cyl('wind_sensor', (-1.40, -0.42, 2.31), 0.055, 0.30,
                        M['metal_dark'], coll, segs=10))
    objs.append(add_box('roof_vent_base', (-1.10, 0.0, 2.187),
                        (0.42, 0.46, 0.022), M['metal_dark'], coll,
                        bevel=0.006))
    objs.append(add_box('roof_vent', (-1.10, 0.0, 2.21), (0.36, 0.40, 0.06),
                        M['paint_dark'], coll, bevel=0.01))
    for sy in (-1, 1):
        objs.append(add_box(f'roof_grab_{sy}', (-0.1, sy * 0.55, 2.21),
                            (0.42, 0.035, 0.035), M['metal'], coll))
        for gx in (-0.18, 0.18):
            objs.append(add_box(f'roof_grableg_{sy}_{gx}',
                                (-0.1 + gx, sy * 0.55, 2.192),
                                (0.03, 0.03, 0.055), M['metal'], coll))

    # triangular unit markings on both turret cheeks
    for sy in (-1, 1):
        base = Vector((1.36, sy * 1.395, 1.62))
        pts = [base + Vector((-0.14, 0, 0.0)),
               base + Vector((0.17, 0, 0.17)),
               base + Vector((-0.14, 0, 0.34))]
        for i in range(3):
            a, b = pts[i], pts[(i + 1) % 3]
            mid = (a + b) / 2
            d = b - a
            ang = math.atan2(d.z, d.x)
            objs.append(add_box(f'tri_{sy}_{i}', tuple(mid),
                                (d.length, 0.012, 0.045), M['paint_dark'],
                                coll, rot=(0, -ang, 0)))

    # bustle rack with stowage
    bx0, bx1 = -2.02, -2.86
    for sy in (-1, 1):
        objs.append(add_box(f'rack_rail_{sy}', ((bx0 + bx1) / 2, sy * 1.22, 2.06),
                            (abs(bx1 - bx0), 0.05, 0.05), M['metal_dark'], coll))
        objs.append(add_box(f'rack_low_{sy}', ((bx0 + bx1) / 2, sy * 1.22, 1.60),
                            (abs(bx1 - bx0), 0.05, 0.05), M['metal_dark'], coll))
        for i in range(4):
            px = bx0 - 0.10 - i * 0.24
            objs.append(add_box(f'rack_v_{sy}_{i}', (px, sy * 1.22, 1.83),
                                (0.035, 0.035, 0.50), M['metal_dark'], coll))
    for i in range(6):
        px = bx0 - 0.10 - i * 0.16
        objs.append(add_box(f'rack_back_{i}', (px, 0, 1.83),
                            (0.035, 2.48, 0.035), M['metal_dark'], coll))
    objs.append(add_box('rack_floor', (-2.44, 0, 1.62), (0.84, 2.44, 0.035),
                        M['metal_dark'], coll))
    # stowed gear
    objs.append(add_box('stow_box1', (-2.38, -0.45, 1.82), (0.66, 0.82, 0.40),
                        M['camo'], coll, bevel=0.03))
    objs.append(add_box('stow_box2', (-2.38, 0.55, 1.80), (0.60, 0.62, 0.35),
                        M['paint_dark'], coll, bevel=0.03))
    objs.append(add_cyl('stow_roll', (-2.42, 0.05, 2.05), 0.16, 1.55,
                        M['green_flag'], coll, axis='Y', segs=18, bevel=0.02))
    # yellow crate with green end panel (as in the reference)
    objs.append(add_box('crate', (-2.52, 0.95, 1.86), (0.50, 0.55, 0.34),
                        M['yellow'], coll, bevel=0.015))
    objs.append(add_box('crate_panel', (-2.78, 0.95, 1.86), (0.02, 0.42, 0.26),
                        M['green_flag'], coll))
    # jerry cans
    for i, jy in enumerate((-1.02, 1.20)):
        objs.append(add_box(f'jerry_{i}', (-2.44, jy, 1.82), (0.26, 0.18, 0.42),
                            M['paint_dark'], coll, bevel=0.03))
    return objs


# ---------------------------------------------------------------- assembly

def build_tank(M, coll, camo_space, yaw=0.12, location=(0, 0, 0)):
    objs = []
    objs += build_hull(M, coll)
    objs += build_turret(M, coll)
    objs += build_running_gear(M, coll)
    objs += build_tracks(M, coll)

    # mud clumps stuck to the running gear and skirts
    import random
    rnd = random.Random(77)
    for i in range(34):
        sy = rnd.choice((-1, 1))
        x = rnd.uniform(-3.3, 3.0)
        z = rnd.uniform(0.28, 0.72)
        y = sy * (1.70 + rnd.uniform(-0.06, 0.06))
        s = rnd.uniform(0.05, 0.14)
        objs.append(add_ico(f'mudclump_{i}', (x, y, z), s, M['mud'], coll,
                            subdiv=1, scale=(1.6, 0.5, 0.7), disp=s * 0.25,
                            seed=i, smooth=False))
    # clods on the hull nose / rear
    for i in range(10):
        x = rnd.uniform(-3.9, 3.9)
        z = rnd.uniform(0.5, 0.9)
        sy = rnd.choice((-1, 1))
        objs.append(add_ico(f'mudclump2_{i}', (x, sy * 1.84, z),
                            rnd.uniform(0.04, 0.09), M['mud'], coll, subdiv=1,
                            scale=(1.0, 0.4, 0.7), disp=0.01, seed=100 + i,
                            smooth=False))

    # apply yaw + placement to the whole tank (geometry is already in world space)
    mat = Matrix.Translation(Vector(location)) @ Matrix.Rotation(yaw, 4, 'Z')
    for ob in objs:
        ob.data.transform(mat)
        ob.data.update()
    camo_space.matrix_world = mat @ camo_space.matrix_world
    return objs
