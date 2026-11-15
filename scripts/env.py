"""Forest road diorama: terrain, pines, ferns, rocks, puddles, fog."""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix, Euler
from utils import (add_box, add_cyl, add_ico, add_loft, rect_ring, mesh_object,
                   collection, srgb, tri_prism)
import mats


TAU = math.pi * 2


# ---------------------------------------------------------------- helpers

def _hash2(ix, iy):
    n = (ix * 374761393 + iy * 668265263) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 4294967295.0


def _vnoise(x, y):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    ux = fx * fx * (3 - 2 * fx)
    uy = fy * fy * (3 - 2 * fy)
    a = _hash2(ix, iy)
    b = _hash2(ix + 1, iy)
    c = _hash2(ix, iy + 1)
    d = _hash2(ix + 1, iy + 1)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def fbm(x, y, octaves=4, lac=2.03, gain=0.5):
    v, amp, norm = 0.0, 1.0, 0.0
    for i in range(octaves):
        v += amp * _vnoise(x, y)
        norm += amp
        amp *= gain
        x *= lac
        y *= lac
    return v / norm


def smoothstep(a, b, x):
    if a == b:
        return 0.0 if x < a else 1.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def road_center(x):
    return 1.15 * math.sin(x / 8.5) + 0.35 * math.sin(x / 3.7 + 1.0)


def road_frame(x):
    y = road_center(x)
    dy = (road_center(x + 0.05) - road_center(x - 0.05)) / 0.1
    return y, dy


# ---------------------------------------------------------------- terrain

class Terrain:
    def __init__(self, xmin=-15.0, xmax=15.0, ymin=-11.0, ymax=11.0, step=0.15):
        self.xmin, self.xmax, self.ymin, self.ymax = xmin, xmax, ymin, ymax
        self.step = step
        self.puddles = [
            (4.9, 0.95, 1.05, 0.10), (7.9, -0.72, 0.85, 0.08),
            (-5.1, -0.95, 0.95, 0.09), (-8.2, 0.62, 0.75, 0.08),
            (-11.6, -0.55, 0.70, 0.07), (10.4, 0.75, 0.65, 0.07),
            (12.3, -0.55, 0.80, 0.08),
        ]
        # correct puddle y to follow the road + rut offset
        self.puddles = [(x, road_center(x) + off, r, d)
                        for (x, off, r, d) in self.puddles]
        self.tank_center = (0.0, 0.0)
        self.h0 = self._raw_height(0.0, 0.0)
        self.flat_r = 5.6

    # ---- height field
    def _raw_height(self, x, y):
        ry = road_center(x)
        s = y - ry
        d = abs(s)
        base = (0.62 * fbm(x * 0.075 + 5.0, y * 0.075 + 3.0, 4) +
                0.20 * fbm(x * 0.22 + 1.0, y * 0.22 + 8.0, 3)) - 0.22
        base *= 0.35 + 0.65 * smoothstep(1.7, 3.4, d)
        road = smoothstep(2.25, 1.55, d)
        h = base - 0.17 * road
        # crown on the road
        h += 0.035 * road * (1.0 - min(1.0, (d / 2.2) ** 2))
        # wheel ruts (wander a little)
        wob = 0.20 * math.sin(x / 2.3 + 1.4)
        for off in (-0.82, 0.82):
            rt = math.exp(-(((s - off - wob) / 0.30) ** 2))
            h -= 0.135 * rt * road
        # puddles: soft depressions
        for (px, py, pr, pd) in self.puddles:
            pd2 = math.hypot(x - px, y - py)
            if pd2 < pr * 1.5:
                h -= pd * (1.0 - smoothstep(pr * 0.35, pr, pd2))
        # low berms just off the road
        berm = math.exp(-(((d - 2.95) / 0.55) ** 2))
        h += 0.18 * berm * (0.5 + fbm(x * 0.4, y * 0.4, 2))
        # fine forest-floor roughness
        h += 0.030 * (fbm(x * 1.6 + 7.0, y * 1.6 + 2.0, 3) - 0.5) * (1.0 - 0.45 * road)
        return h

    def height(self, x, y):
        h = self._raw_height(x, y)
        # flatten under the tank so the tracks sit cleanly
        tx, ty = self.tank_center
        dd = math.hypot(x - tx, y - ty)
        f = smoothstep(self.flat_r + 1.5, self.flat_r - 1.2, dd)
        return h * (1 - f) + self.h0 * f

    def normal_ish(self, x, y, e=0.18):
        hx = self.height(x + e, y) - self.height(x - e, y)
        hy = self.height(x, y + e) - self.height(x, y - e)
        return Vector((-hx / (2 * e), -hy / (2 * e), 1.0)).normalized()

    # ---- build mesh
    def build(self, M, coll, side_coll):
        nx = int((self.xmax - self.xmin) / self.step) + 1
        ny = int((self.ymax - self.ymin) / self.step) + 1
        verts = []
        for j in range(ny):
            y = self.ymin + j * self.step
            for i in range(nx):
                x = self.xmin + i * self.step
                verts.append((x, y, self.height(x, y)))
        faces = []
        for j in range(ny - 1):
            for i in range(nx - 1):
                a = j * nx + i
                b = a + 1
                c = a + nx + 1
                d = a + nx
                faces.append((a, b, c, d))
        ob = mesh_object('Terrain', verts, faces, M['terrain'], coll, smooth=True)

        # vertex colours + wet mask
        ob.data.color_attributes.new(name='Col', type='FLOAT_COLOR',
                                     domain='POINT')
        ob.data.attributes.new(name='Wet', type='FLOAT', domain='POINT')
        ob.data.attributes.new(name='Road', type='FLOAT', domain='POINT')
        # re-fetch after adding all layers (references can go stale)
        col_attr = ob.data.color_attributes['Col']
        wet_attr = ob.data.attributes['Wet']
        road_attr = ob.data.attributes['Road']
        cols, wets, roads = [], [], []
        for idx, v in enumerate(ob.data.vertices):
            x, y, z = v.co
            ry = road_center(x)
            s = y - ry
            d = abs(s)
            road = smoothstep(2.35, 1.6, d)
            wob = 0.20 * math.sin(x / 2.3 + 1.4)
            rut = max(math.exp(-(((s - 0.82 - wob) / 0.40) ** 2)),
                      math.exp(-(((s + 0.82 - wob) / 0.40) ** 2)))
            n1 = fbm(x * 0.30 + 11, y * 0.30 + 4, 3)
            n2 = fbm(x * 1.6 + 3, y * 1.6 + 17, 3)
            n3 = fbm(x * 0.10 + 31, y * 0.10 + 9, 3)
            # forest floor: leaf litter + moss
            litter = srgb('241A10')
            soil = srgb('1A120B')
            moss = srgb('253114')
            dryleaf = srgb('332414')
            base = [litter[k] * (0.7 + 0.6 * n1) for k in range(3)]
            if n2 > 0.52:
                f = smoothstep(0.52, 0.72, n2) * 0.75
                base = [base[k] * (1 - f) + moss[k] * f for k in range(3)]
            if n3 > 0.60:
                f = smoothstep(0.60, 0.78, n3) * 0.45
                base = [base[k] * (1 - f) + dryleaf[k] * f for k in range(3)]
            # road mud
            mud = srgb('342516')
            mud_dark = srgb('1D150D')
            mudc = [mud[k] * (0.72 + 0.5 * n1) for k in range(3)]
            if rut > 0.3:
                f = min(1.0, rut) * 0.8
                mudc = [mudc[k] * (1 - f) + mud_dark[k] * f for k in range(3)]
            f = road
            c = [base[k] * (1 - f) + mudc[k] * f for k in range(3)]
            # wetness: ruts + puddles
            wet = rut * road * 0.55
            for (px, py, pr, pd) in self.puddles:
                dd = math.hypot(x - px, y - py)
                if dd < pr * 1.6:
                    wet = max(wet, (1.0 - smoothstep(pr * 0.5, pr * 1.5, dd)) * 0.95)
            wet = max(0.0, min(1.0, wet))
            c = [c[k] * (1 - wet * 0.45) + srgb('17120C')[k] * wet * 0.45
                 for k in range(3)]
            cols.extend((c[0], c[1], c[2], 1.0))
            wets.append(wet)
            roads.append(road)
        col_attr.data.foreach_set('color', cols)
        wet_attr.data.foreach_set('value', wets)
        road_attr.data.foreach_set('value', roads)
        ob.data.update()

        # side skirt of the diorama slab (cut soil), plus a bottom
        bverts, bfaces = [], []
        boundary = []
        for i in range(nx):
            boundary.append((i, 0))
        for j in range(1, ny):
            boundary.append((nx - 1, j))
        for i in range(nx - 2, -1, -1):
            boundary.append((i, ny - 1))
        for j in range(ny - 2, 0, -1):
            boundary.append((0, j))
        bottom = -1.55
        idxmap = {}
        for (i, j) in boundary:
            idx = j * nx + i
            x, y, z = verts[idx]
            idxmap[(i, j)] = len(bverts)
            bverts.append((x, y, z))
        for (i, j) in boundary:
            x, y, z = verts[j * nx + i]
            bverts.append((x, y, bottom))
        n = len(boundary)
        for k in range(n):
            k2 = (k + 1) % n
            a = k
            b = k2
            c = n + k2
            d = n + k
            bfaces.append((a, d, c, b))
        bfaces.append(tuple(range(2 * n - 1, n - 1, -1)))
        bs = mesh_object('DioramaSoil', bverts, bfaces, M['soil'], side_coll,
                         smooth=False)
        return ob, bs

    # ---- puddle meshes
    def build_puddles(self, M, coll):
        objs = []
        for pi, (px, py, pr, pd) in enumerate(self.puddles):
            verts = [(px, py, self.height(px, py) + 0.018)]
            faces = []
            n = 40
            rnd = random.Random(900 + pi)
            radii = [pr * (0.72 + 0.28 * _vnoise(math.cos(TAU * i / n) * 1.7 + pi * 5,
                                                 math.sin(TAU * i / n) * 1.7)) for i in range(n)]
            for i in range(n):
                a = TAU * i / n
                r = radii[i] * (0.85 + 0.3 * rnd.random())
                x = px + math.cos(a) * r
                y = py + math.sin(a) * r
                verts.append((x, y, self.height(px, py) + 0.018 +
                              0.002 * math.sin(a * 3)))
                faces.append((0, 1 + i, 1 + (i + 1) % n))
            ob = mesh_object(f'Puddle_{pi}', verts, faces, M['water'], coll,
                             smooth=True)
            objs.append(ob)

        # shallow water films in the wheel ruts
        rnd = random.Random(5150)
        for pi, (px, off, ln, wd) in enumerate([
                (-2.2, 0.82, 1.7, 0.30), (0.6, -0.82, 2.2, 0.34),
                (3.2, 0.82, 1.4, 0.26), (5.8, -0.82, 1.8, 0.28),
                (-6.4, 0.82, 1.5, 0.25), (8.4, 0.82, 1.2, 0.22),
                (-9.6, -0.82, 1.3, 0.24), (11.2, -0.82, 1.1, 0.20)]):
            cy = road_center(px) + off
            zc = self.height(px, cy) + 0.010
            verts = [(px, cy, zc)]
            faces = []
            n = 28
            for i in range(n):
                a = TAU * i / n
                rr = 0.8 + 0.35 * rnd.random()
                x = px + math.cos(a) * ln * 0.5 * rr
                y = cy + math.sin(a) * wd * 0.5 * rr
                verts.append((x, y, zc))
                faces.append((0, 1 + i, 1 + (i + 1) % n))
            objs.append(mesh_object(f'RutWater_{pi}', verts, faces, M['water'],
                                    coll, smooth=True))
        return objs


# ---------------------------------------------------------------- trees

def _add_tube(bm, pts, radii, sides=7, cap=True, rough=0.0):
    rings = []
    for i, (p, r) in enumerate(zip(pts, radii)):
        if i == 0:
            t = (Vector(pts[1]) - Vector(pts[0])).normalized()
        elif i == len(pts) - 1:
            t = (Vector(pts[-1]) - Vector(pts[-2])).normalized()
        else:
            t = (Vector(pts[i + 1]) - Vector(pts[i - 1])).normalized()
        up = Vector((0, 0, 1))
        if abs(t.dot(up)) > 0.95:
            up = Vector((1, 0, 0))
        n1 = t.cross(up).normalized()
        n2 = t.cross(n1).normalized()
        ring = []
        for k in range(sides):
            a = TAU * k / sides
            rr = r
            if rough > 0:
                rr *= 1.0 + rough * (0.62 * math.sin(k * 5.7 + p[2] * 2.6) +
                                     0.38 * math.sin(k * 2.3 + p[2] * 7.1))
            ring.append(bm.verts.new(Vector(p) + (n1 * math.cos(a) + n2 * math.sin(a)) * rr))
        rings.append(ring)
    bm.verts.index_update()
    for i in range(len(rings) - 1):
        for k in range(sides):
            a = rings[i][k]
            b = rings[i][(k + 1) % sides]
            c = rings[i + 1][(k + 1) % sides]
            d = rings[i + 1][k]
            bm.faces.new((a, b, c, d))
    if cap:
        bm.faces.new(tuple(reversed(rings[0])))
    return rings


def _add_needle_cluster(bm, center, size, direction, rnd, droop=0.0):
    """A few crossed alpha cards carrying a painted pine bough."""
    d = Vector(direction)
    d.z = max(-0.35, min(0.35, d.z))
    if d.length < 1e-4:
        d = Vector((1, 0, 0))
    d.normalize()
    up = Vector((0, 0, 1))
    if abs(d.dot(up)) > 0.93:
        up = Vector((1, 0, 0))
    up = (up - d * up.dot(d)).normalized()
    side = d.cross(up).normalized()
    c = Vector(center)
    L = max(0.50, size[0] * 1.95)
    H = max(0.40, size[0] * 1.55)
    uv_layer = bm.loops.layers.uv.verify()
    ncards = 5
    for ci in range(ncards):
        roll = ci * math.pi / ncards + rnd.uniform(-0.18, 0.18)
        u = (up * math.cos(roll) + side * math.sin(roll)).normalized()
        a = c - d * (L * 0.5) - u * (H * 0.5)
        b = c + d * (L * 0.5) - u * (H * 0.5)
        e = c + d * (L * 0.5) + u * (H * 0.5)
        f = c - d * (L * 0.5) + u * (H * 0.5)
        vs = [bm.verts.new(p) for p in (a, b, e, f)]
        face = bm.faces.new(vs)
        uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
        for loop, uv in zip(face.loops, uvs):
            loop[uv_layer].uv = uv
    return None


def build_pine(M, coll, x, y, z, height, seed=0, lean=(0.02, 0.01)):
    rnd = random.Random(seed)
    trunk_bm = bmesh.new()
    needle_bm = bmesh.new()
    base = Vector((x, y, z - 0.08))
    # trunk: gently curving, tapering, with a root flare
    nseg = 12
    pts = []
    radii = []
    for i in range(nseg + 1):
        t = i / nseg
        px = x + lean[0] * height * (t ** 1.35) + 0.10 * math.sin(t * 4 + seed)
        py = y + lean[1] * height * (t ** 1.35) + 0.10 * math.cos(t * 3 + seed)
        pz = base.z + height * t
        pts.append((px, py, pz))
        r = 0.34 * (1.0 - 0.84 * t) ** 1.1 + 0.035
        if i == 0:
            r *= 1.75
        radii.append(r)
    _add_tube(trunk_bm, pts, radii, sides=10, rough=0.10)
    trunk_ob = mesh_object(f'PineTrunk_{seed}', [], [], M['bark'], coll,
                           smooth=True)
    # to avoid expensive bmesh->mesh each time, write at the end
    # roots
    for i in range(5):
        a = TAU * i / 5 + rnd.uniform(-0.4, 0.4)
        p0 = (x + math.cos(a) * 0.25, y + math.sin(a) * 0.25, z + 0.05)
        p1 = (x + math.cos(a) * 0.9, y + math.sin(a) * 0.9, z - 0.18)
        p2 = (x + math.cos(a) * 1.5, y + math.sin(a) * 1.5, z - 0.28)
        _add_tube(trunk_bm, [p0, p1, p2], [0.18, 0.11, 0.03], sides=5)

    # branches in whorls
    whorls = 5
    for wi in range(whorls):
        t = 0.42 + 0.50 * (wi / (whorls - 1))
        t += rnd.uniform(-0.025, 0.025)
        wz = base.z + height * t
        # trunk position at this height
        tx = x + lean[0] * height * (t ** 1.35)
        ty = y + lean[1] * height * (t ** 1.35)
        nb = rnd.randint(4, 6)
        base_ang = rnd.uniform(0, TAU)
        for bi in range(nb):
            a = base_ang + TAU * bi / nb + rnd.uniform(-0.3, 0.3)
            L = (2.0 + 2.6 * (1 - t)) * (0.75 + rnd.uniform(0, 0.5))
            L *= (height / 20.0) ** 0.5
            rise = rnd.uniform(-0.15, 0.5)
            droop = rnd.uniform(0.15, 0.65)
            # branch as 4-point curve
            bp = []
            br = []
            for si in range(4):
                u = si / 3
                bx = tx + math.cos(a) * L * u
                by = ty + math.sin(a) * L * u
                bz = wz + rise * u * L * -0.15 + 0.10 - droop * (u ** 2) * L * 0.22
                bp.append((bx, by, bz))
                br.append(0.10 * (1 - 0.75 * u) + 0.012)
            _add_tube(trunk_bm, bp, br, sides=5, rough=0.03)
            # needle tufts along the outer 65% of the branch
            npads = rnd.randint(7, 9)
            for pi in range(npads):
                u = 0.30 + 0.70 * (pi / max(1, npads - 1)) + rnd.uniform(-0.05, 0.05)
                u = min(1.0, u)
                cx = tx + math.cos(a) * L * u
                cy = ty + math.sin(a) * L * u
                cz = wz - droop * (u ** 2) * L * 0.22 + rnd.uniform(-0.15, 0.25)
                length = (0.62 + rnd.uniform(0, 0.42)) * (1.0 - 0.20 * u)
                length *= (height / 20.0) ** 0.6
                width = length * rnd.uniform(0.40, 0.56)
                thick = width * rnd.uniform(0.60, 0.85)
                dirv = Vector((math.cos(a + rnd.uniform(-0.65, 0.65)),
                               math.sin(a + rnd.uniform(-0.65, 0.65)), 0.04))
                _add_needle_cluster(needle_bm, (cx, cy, cz),
                                    (length, width, thick), dirv, rnd,
                                    droop=rnd.uniform(-0.08, 0.18))
        # top crown tufts
    for i in range(12):
        a = rnd.uniform(0, TAU)
        rr = rnd.uniform(0.2, 1.8) * (height / 20.0)
        cx = x + math.cos(a) * rr + lean[0] * height * 0.9
        cy = y + math.sin(a) * rr + lean[1] * height * 0.9
        cz = base.z + height * rnd.uniform(0.92, 1.02)
        s = rnd.uniform(0.9, 1.6) * (height / 20.0)
        _add_needle_cluster(needle_bm, (cx, cy, cz), (s, s * 0.55, s * 0.45),
                            (math.cos(a), math.sin(a), 0.0), rnd)

    trunk_ob.data.clear_geometry()
    trunk_bm.to_mesh(trunk_ob.data)
    trunk_bm.free()
    trunk_ob.data.update()
    for p in trunk_ob.data.polygons:
        p.use_smooth = True

    needles = bpy.data.objects.new(f'PineNeedles_{seed}', bpy.data.meshes.new(f'PineNeedles_{seed}'))
    needle_bm.to_mesh(needles.data)
    needle_bm.free()
    needles.data.materials.append(M['pine_card'])
    coll.objects.link(needles)
    for p in needles.data.polygons:
        p.use_smooth = False
    return trunk_ob, needles


# ---------------------------------------------------------------- ferns / grass

def build_fern(M, coll, x, y, z, height, seed=0):
    rnd = random.Random(seed)
    bm = bmesh.new()
    nfr = rnd.randint(9, 13)
    for f in range(nfr):
        yaw = TAU * f / nfr + rnd.uniform(-0.2, 0.2)
        tilt = rnd.uniform(0.45, 1.1)  # from vertical
        droop = rnd.uniform(0.15, 0.55)
        length = height * rnd.uniform(0.72, 1.08)
        frond_verts = []
        # local frond space: +X out, Z up
        spine = []
        nseg = 8
        pts3 = []
        for i in range(nseg + 1):
            t = i / nseg
            px = length * t * math.sin(tilt * 0.55)
            pz = length * (t * math.cos(tilt * 0.55) -
                           droop * (t ** 2.4) * 0.55)
            pts3.append((px, 0.0, pz))
        # stem ribbon
        for i in range(nseg):
            t0 = i / nseg
            t1 = (i + 1) / nseg
            w0 = 0.014 * (1 - 0.6 * t0) * height
            w1 = 0.014 * (1 - 0.6 * t1) * height
            a = bm.verts.new(pts3[i]); a.co.y -= w0
            b = bm.verts.new(pts3[i]); b.co.y += w0
            c = bm.verts.new(pts3[i + 1]); c.co.y += w1
            d = bm.verts.new(pts3[i + 1]); d.co.y -= w1
            bm.faces.new((a, b, c, d))
            frond_verts += [a, b, c, d]
        # leaflets
        nleaf = 15
        for i in range(nleaf):
            t = 0.14 + 0.84 * (i / (nleaf - 1))
            idx = min(nseg, int(t * nseg))
            base = Vector(pts3[idx])
            frac = t * nseg - idx
            if idx < nseg:
                base = base.lerp(Vector(pts3[idx + 1]), frac)
            leaf_len = (0.19 * (1 - t) ** 0.55 + 0.03) * height
            ang = math.radians(50 + 22 * t)
            for side in (-1, 1):
                dirv = Vector((math.cos(ang) * 0.6, side * math.sin(ang), 0.16))
                dirv.normalize()
                perp = dirv.cross(Vector((0, 0, 1))).normalized()
                w = leaf_len * 0.20
                p0 = base + Vector((0.005, side * 0.006, 0.0))
                p1 = base + dirv * (leaf_len * 0.34) + perp * w
                p2 = base + dirv * leaf_len + Vector((0, 0, 0.006))
                p3 = base + dirv * (leaf_len * 0.34) - perp * w
                vs = [bm.verts.new(p) for p in (p0, p1, p2, p3)]
                bm.faces.new(vs)
                frond_verts += vs
        # rotate around Z and place (only the frond just built)
        Mrot = Matrix.Rotation(yaw, 4, 'Z')
        for v in frond_verts:
            v.co = Mrot @ v.co + Vector((x, y, z))
    ob = mesh_object(f'Fern_{seed}', [], [], M['fern'], coll, smooth=True)
    ob.data.clear_geometry()
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def build_grass(M, coll, x, y, z, size, seed):
    rnd = random.Random(seed)
    verts, faces = [], []
    n = rnd.randint(7, 13)
    for b in range(n):
        a = rnd.uniform(0, TAU)
        h = size * rnd.uniform(0.6, 1.3)
        lean = rnd.uniform(0.15, 0.5)
        w = size * 0.035
        p0 = Vector((x + math.cos(a) * 0.02, y + math.sin(a) * 0.02, z))
        segs = 3
        prev = None
        for i in range(segs + 1):
            t = i / segs
            p = p0 + Vector((math.cos(a) * lean * h * t * t,
                             math.sin(a) * lean * h * t * t,
                             h * t - 0.35 * h * (t ** 3)))
            ww = w * (1 - t * 0.85)
            if i == 0:
                v1 = len(verts); verts.append((p.x - ww, p.y, p.z))
                v2 = len(verts); verts.append((p.x + ww, p.y, p.z))
                prev = (v1, v2, p)
            else:
                v1 = len(verts); verts.append((p.x - ww, p.y, p.z))
                v2 = len(verts); verts.append((p.x + ww, p.y, p.z))
                faces.append((prev[0], prev[1], v2, v1))
                prev = (v1, v2, p)
    return mesh_object(f'Grass_{seed}', verts, faces, M['grass'], coll,
                       smooth=True)


# ---------------------------------------------------------------- rocks & logs

def build_rocks(M, coll, terrain, rocks):
    objs = []
    for i, (x, y, scale) in enumerate(rocks):
        z = terrain.height(x, y)
        sz = scale
        ob = add_ico(f'Rock_{i}', (x, y, z - sz * 0.18),
                     sz, M['rock'], coll, subdiv=3,
                     scale=(1.0, 0.8 + (i % 3) * 0.12, 0.62),
                     rot=(0, 0, i * 1.7), disp=sz * 0.24, seed=500 + i,
                     smooth=True)
        # flatten the underside a little
        for v in ob.data.vertices:
            if v.co.z < z - sz * 0.05:
                v.co.z = z - sz * 0.05
        ob.data.update()
        objs.append(ob)
    return objs


def build_log(M, coll, terrain, x, y, length, radius, rot_z, seed):
    z = terrain.height(x, y)
    objs = []
    log = add_cyl(f'Log_{seed}', (x, y, z + radius * 0.6), radius, length,
                  M['bark'], coll, axis='X', segs=14, r2=radius * 0.8,
                  rot=(0, 0, rot_z), smooth=True)
    objs.append(log)
    # moss blobs on top
    rnd = random.Random(seed)
    for i in range(6):
        t = rnd.uniform(-0.45, 0.45)
        lx = x + math.cos(rot_z) * length * t
        ly = y + math.sin(rot_z) * length * t
        objs.append(add_ico(f'LogMoss_{seed}_{i}', (lx, ly, z + radius * 1.15),
                            radius * rnd.uniform(0.35, 0.6), M['rock'], coll,
                            subdiv=2, scale=(1.4, 0.9, 0.28),
                            disp=0.03, seed=seed * 10 + i))
    return objs


# ---------------------------------------------------------------- forest floor

def scatter_needles(M, coll, terrain, trees, count=3200):
    rnd = random.Random(4242)
    verts, faces = [], []
    for i in range(count):
        # bias towards the trees
        if trees and rnd.random() < 0.78:
            tx, ty, th = trees[rnd.randrange(len(trees))]
            rr = abs(rnd.gauss(0, 4.0))
            x = tx + rnd.uniform(-rr, rr)
            y = ty + rnd.uniform(-rr, rr)
        else:
            x = rnd.uniform(-14.5, 14.5)
            y = rnd.uniform(-10.5, 10.5)
        d = abs(y - road_center(x))
        if d < 2.1 and rnd.random() < 0.75:
            continue
        z = terrain.height(x, y) + 0.012
        L = rnd.uniform(0.05, 0.13)
        a = rnd.uniform(0, TAU)
        w = L * 0.035
        dx, dy = math.cos(a) * L, math.sin(a) * L
        nx, ny = -math.sin(a) * w, math.cos(a) * w
        b = len(verts)
        verts += [(x - dx - nx, y - dy - ny, z),
                  (x - dx + nx, y - dy + ny, z),
                  (x + dx + nx, y + dy + ny, z + 0.01),
                  (x + dx - nx, y + dy - ny, z + 0.01)]
        faces.append((b, b + 1, b + 2, b + 3))
    return mesh_object('NeedleLitter', verts, faces, M['mud'], coll, smooth=False)


def scatter_leaf_litter(M, coll, terrain, trees, count=4200):
    rnd = random.Random(6161)
    verts, faces, cols = [], [], []
    palette = [srgb('3B2A18'), srgb('4A3520'), srgb('5A4022'),
               srgb('2E2214'), srgb('6B4B26'), srgb('261D12')]
    for i in range(count):
        if trees and rnd.random() < 0.72:
            tx, ty, th = trees[rnd.randrange(len(trees))]
            x = tx + rnd.gauss(0, 3.6)
            y = ty + rnd.gauss(0, 3.6)
        else:
            x = rnd.uniform(-14.4, 14.4)
            y = rnd.uniform(-10.4, 10.4)
        if not (-14.5 < x < 14.5 and -10.5 < y < 10.5):
            continue
        d = abs(y - road_center(x))
        if d < 2.1 and rnd.random() < 0.6:
            continue
        z = terrain.height(x, y) + 0.010 + rnd.uniform(0, 0.006)
        L = rnd.uniform(0.05, 0.13)
        W = L * rnd.uniform(0.35, 0.55)
        a = rnd.uniform(0, TAU)
        dx, dy = math.cos(a) * L, math.sin(a) * L
        px, py = -math.sin(a) * W, math.cos(a) * W
        b = len(verts)
        verts += [(x - dx, y - dy, z),
                  (x + px, y + py, z + L * 0.05),
                  (x + dx, y + dy, z),
                  (x - px, y - py, z)]
        faces.append((b, b + 1, b + 2, b + 3))
        c = rnd.choice(palette)
        mult = rnd.uniform(0.7, 1.15)
        cols += [c[0] * mult, c[1] * mult, c[2] * mult, 1.0] * 4
    ob = mesh_object('LeafLitter', verts, faces, M['leaf'], coll, smooth=False)
    ca = ob.data.color_attributes.new(name='Col', type='FLOAT_COLOR',
                                      domain='POINT')
    ca = ob.data.color_attributes['Col']
    ca.data.foreach_set('color', cols)
    ob.data.update()
    return ob


def scatter_twigs(M, coll, terrain, count=90):
    rnd = random.Random(8282)
    bm = bmesh.new()
    for i in range(count):
        x = rnd.uniform(-14, 14)
        y = rnd.uniform(-10, 10)
        z = terrain.height(x, y)
        a = rnd.uniform(0, TAU)
        L = rnd.uniform(0.2, 0.8)
        p0 = (x, y, z + 0.01)
        p1 = (x + math.cos(a) * L * 0.5, y + math.sin(a) * L * 0.5,
              z + 0.02 + rnd.uniform(0, 0.02))
        p2 = (x + math.cos(a) * L, y + math.sin(a) * L, z + 0.008)
        r = rnd.uniform(0.008, 0.020)
        _add_tube(bm, [p0, p1, p2], [r, r * 0.7, r * 0.35], sides=4)
    ob = bpy.data.objects.new('Twigs', bpy.data.meshes.new('Twigs'))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.materials.append(M['bark'])
    coll.objects.link(ob)
    return ob


def scatter_stones(M, coll, terrain, count=140):
    rnd = random.Random(777)
    objs = []
    bm = bmesh.new()
    for i in range(count):
        x = rnd.uniform(-14, 14)
        # bias to road
        y = road_center(x) + rnd.uniform(-2.2, 2.2)
        z = terrain.height(x, y)
        s = rnd.uniform(0.022, 0.09)
        res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=s)
        for v in res['verts']:
            v.co = Vector((v.co.x * 1.4 + x, v.co.y * 1.1 + y,
                           v.co.z * 0.55 + z + s * 0.2))
    ob = bpy.data.objects.new('RoadStones', bpy.data.meshes.new('RoadStones'))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.materials.append(M['stone'])
    coll.objects.link(ob)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def build_forest(M):
    tcoll = collection('TREES')
    dcoll = collection('DETAILS')
    terrain = Terrain()
    ter, soil = terrain.build(M, collection('TERRAIN'), collection('TERRAIN'))
    puddles = terrain.build_puddles(M, collection('TERRAIN'))

    trees_info = [
        # x, y, height, leanx, leany, seed
        (-13.2, 8.0, 23.0, 0.018, -0.012, 11),
        (-8.4, 9.4, 19.5, -0.010, 0.016, 12),
        (-3.4, 8.8, 21.0, 0.014, 0.004, 13),
        (2.8, 9.8, 18.0, -0.006, 0.020, 14),
        (8.8, 8.4, 22.0, 0.012, -0.006, 15),
        (14.2, 4.6, 20.0, -0.018, 0.006, 16),
        (14.6, -6.2, 21.5, 0.008, 0.014, 17),
        (14.4, -8.8, 19.0, -0.012, -0.010, 18),
        (-8.0, -9.8, 20.5, 0.016, 0.010, 19),
        (-12.2, -8.6, 18.5, -0.008, -0.016, 20),
        (-14.2, -2.0, 22.5, 0.010, 0.006, 21),
        (-2.2, -10.4, 17.5, -0.014, 0.008, 22),
        (-0.5, -10.8, 18.0, 0.010, -0.012, 23),
    ]
    trunks = []
    needles = []
    tree_xy = []
    for (x, y, h, lx, ly, seed) in trees_info:
        z = terrain.height(x, y)
        tr, nd = build_pine(M, tcoll, x, y, z, h, seed=seed, lean=(lx, ly))
        trunks.append(tr)
        needles.append(nd)
        tree_xy.append((x, y, h))

    # a few smaller trees / saplings closer in
    for i, (x, y, h, seed) in enumerate([
            (5.6, 4.8, 9.0, 31), (-6.0, 5.4, 7.5, 32),
            (9.2, 3.4, 8.0, 33), (-9.4, -4.6, 10.0, 34),
            (10.8, -4.6, 8.5, 35), (-2.6, 6.4, 6.5, 36)]):
        z = terrain.height(x, y)
        tr, nd = build_pine(M, tcoll, x, y, z, h, seed=seed,
                            lean=(0.02 * (i % 2 * 2 - 1), 0.01))
        trunks.append(tr)
        needles.append(nd)
        tree_xy.append((x, y, h))

    # dark background trees along the far edge to close off the horizon
    for i, (x, y, h, seed) in enumerate([
            (0.5, 10.3, 7.0, 41), (5.5, 10.2, 6.5, 42),
            (-6.0, 10.2, 7.5, 43), (10.8, 9.8, 6.0, 44),
            (-11.2, 10.1, 6.5, 45), (14.2, 9.3, 7.0, 46)]):
        z = terrain.height(x, y)
        tr, nd = build_pine(M, tcoll, x, y, z, h, seed=seed,
                            lean=(0.01, -0.012))
        trunks.append(tr)
        needles.append(nd)
        tree_xy.append((x, y, h))

    # ferns
    ferns = []
    rnd = random.Random(3001)
    fern_spots = []
    for (x, y, h) in [
            (4.6, 2.4, 0.95), (5.8, 2.0, 0.8), (-3.9, 2.7, 0.9),
            (-5.2, 2.1, 0.75), (2.4, -2.9, 0.95), (0.5, 3.4, 0.8),
            (-1.8, -3.1, 0.85), (7.2, -2.6, 1.0), (-7.5, 2.9, 0.85),
            (9.8, 2.2, 0.8), (-10.6, 2.1, 0.95), (11.4, -2.8, 0.85),
            (3.2, 4.5, 1.1), (-4.4, -4.4, 1.0), (6.4, 4.9, 0.95),
            (-11.0, -3.4, 0.85), (12.8, 1.4, 0.7), (-13.0, 1.2, 0.8)]:
        z = terrain.height(x, y)
        ferns.append(build_fern(M, dcoll, x, y, z, h, seed=int(400 + len(ferns))))
        fern_spots.append((x, y))
    for i in range(18):
        x = rnd.uniform(-13, 13)
        y = rnd.uniform(-9.5, 9.5)
        if abs(y - road_center(x)) < 2.6:
            continue
        z = terrain.height(x, y)
        ferns.append(build_fern(M, dcoll, x, y, z,
                                rnd.uniform(0.55, 1.0), seed=700 + i))

    # grass tufts along the verges
    for i in range(80):
        x = rnd.uniform(-14, 14)
        d = rnd.uniform(1.9, 3.2)
        y = road_center(x) + rnd.choice((-1, 1)) * d
        z = terrain.height(x, y)
        build_grass(M, dcoll, x, y, z, rnd.uniform(0.30, 0.70), 900 + i)

    # rocks
    rocks = []
    for (x, y, s) in [
            (2.0, 2.0, 0.55), (3.3, -2.5, 0.7), (-2.7, -2.2, 0.6),
            (-4.8, 2.6, 0.8), (6.6, 2.5, 0.9), (-7.2, 3.0, 0.7),
            (8.6, -3.2, 0.55), (-9.5, 2.5, 0.65), (10.6, 2.9, 0.7),
            (-11.8, -2.6, 0.8), (4.0, 4.2, 0.9), (-2.0, 4.6, 0.75),
            (12.6, -1.2, 0.5), (-13.4, 2.2, 0.6), (0.8, -4.2, 0.5),
            (-6.6, -4.4, 0.6), (5.4, -4.6, 0.55), (13.0, 2.0, 0.55)]:
        rocks.append((x, y, s))
    for i in range(22):
        x = rnd.uniform(-13.5, 13.5)
        y = rnd.uniform(-9.5, 9.5)
        if abs(y - road_center(x)) < 2.0:
            continue
        rocks.append((x, y, rnd.uniform(0.18, 0.5)))
    build_rocks(M, dcoll, terrain, rocks)

    # fallen logs near the verges
    build_log(M, dcoll, terrain, 5.0, 5.0, 4.0, 0.34, math.radians(24), 61)
    build_log(M, dcoll, terrain, -9.0, -4.2, 3.5, 0.28, math.radians(-38), 62)
    build_log(M, dcoll, terrain, 11.5, 4.0, 3.0, 0.24, math.radians(72), 63)

    # stumps
    for i, (x, y) in enumerate([(-10.5, 5.5), (8.0, -6.0), (1.5, 6.0)]):
        z = terrain.height(x, y)
        add_cyl(f'Stump_{i}', (x, y, z + 0.55), 0.32, 1.1, M['bark'], dcoll,
                segs=12, r2=0.26, bevel=0.03)

    scatter_needles(M, dcoll, terrain, tree_xy, count=3400)
    scatter_stones(M, dcoll, terrain, count=90)
    scatter_leaf_litter(M, dcoll, terrain, tree_xy, count=4200)
    scatter_twigs(M, dcoll, terrain, count=90)

    # a few pine cones
    for i in range(34):
        x = rnd.uniform(-12, 12)
        y = rnd.uniform(-8, 8)
        if abs(y - road_center(x)) < 2.0:
            continue
        z = terrain.height(x, y)
        add_ico(f'Cone_{i}', (x, y, z + 0.08), 0.09, M['bark'], dcoll,
                subdiv=1, scale=(1.0, 1.0, 1.5), rot=(rnd.uniform(0, 1), 0,
                                                    rnd.uniform(0, 6)),
                disp=0.02, seed=1000 + i, smooth=False)

    return terrain, ter, soil, trunks, needles, ferns, puddles
