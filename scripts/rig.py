"""Animation rig for the tank: turret / gun / wheels / track controls."""
import bpy
import math
import re
from mathutils import Vector, Matrix

TURRET_PREFIXES = (
    'Turret', 'turret_ring', 'citv_', 'gps_', 'cupola', 'loader_hatch',
    'm2_', 'm240_', 'mg_', 'ant', 'flag_', 'smoke_', 'era_', 'sidebox_',
    'lift_', 'sparelink_', 'wind_sensor', 'roof_', 'stow_', 'crate',
    'jerry_', 'rack_', 'tri_', 'mrs',
)
GUN_PREFIXES = ('gun_', 'mantlet', '_mrs')
WHEEL_PREFIXES = ('tire_', 'rim_', 'rimin_', 'hub_')
IDLER_PREFIXES = ('idler',)
SPROCKET_PREFIXES = ('sprocket', 'sptooth')


def _empty(coll, name, loc=(0, 0, 0), size=0.03, kind='PLAIN_AXES'):
    o = bpy.data.objects.new(name, None)
    o.empty_display_type = kind
    o.empty_display_size = size
    coll.objects.link(o)
    o.location = loc
    return o


def _keep_parent(ob, parent):
    # matrix_world can be stale before a depsgraph update; top-level objects
    # (the common case here) are exactly their basis matrix.
    mw = ob.matrix_basis.copy() if ob.parent is None else ob.matrix_world.copy()
    ob.parent = parent
    ob.matrix_world = mw


def _limit_rot(ob, x=None, y=None, z=None):
    c = ob.constraints.new('LIMIT_ROTATION')
    c.owner_space = 'LOCAL'
    if x is None:
        c.use_limit_x = False
    else:
        c.use_limit_x = True
        c.min_x, c.max_x = [math.radians(v) for v in x]
    if y is None:
        c.use_limit_y = False
    else:
        c.use_limit_y = True
        c.min_y, c.max_y = [math.radians(v) for v in y]
    if z is None:
        c.use_limit_z = False
    else:
        c.use_limit_z = True
        c.min_z, c.max_z = [math.radians(v) for v in z]
    c.use_transform_limit = False
    return c


def _wheel_driver(pivot, hull, radius):
    fc = pivot.driver_add('rotation_euler', 1)
    drv = fc.driver
    drv.type = 'SCRIPTED'
    var = drv.variables.new()
    var.name = 'travel'
    var.type = 'SINGLE_PROP'
    var.targets[0].id = hull
    var.targets[0].data_path = 'location[1]'
    drv.expression = '-travel/%.7f' % max(radius, 1e-5)


def _label(coll, text, loc, size=0.012, rot=(math.radians(90), 0, 0)):
    cur = bpy.data.curves.new('lbl_' + text, 'FONT')
    cur.body = text
    cur.size = size
    cur.align_x = 'CENTER'
    cur.extrude = 0.0002
    ob = bpy.data.objects.new('LBL_' + text, cur)
    ob.location = loc
    ob.rotation_euler = rot
    ob.hide_render = True
    coll.objects.link(ob)
    return ob


def build_rig(tank_coll, yaw, scale, x_front=3.28, x_rear=-3.28):
    """Build controls after the scene has been scaled to 1:35.

    Local frame (after the world is turned +90 so forward = +Y):
      turret yaw   -> local Z
      gun elevation-> local X (-10..+20)
      hull travel  -> local Y (parent space of CTRL_Hull)
      wheels       -> local Y (axle)
    """
    rig = bpy.data.collections.new('RIG')
    bpy.context.scene.collection.children.link(rig)
    objs = [o for o in tank_coll.objects if o.type == 'MESH']
    by_name = {o.name: o for o in objs}
    used = set()

    root = _empty(rig, 'TANK_ROOT', (0, 0, 0), 0.08, 'ARROWS')
    root.rotation_euler[2] = math.radians(-90) + yaw
    root['note'] = 'Tank local Y = forward'
    bpy.context.view_layer.update()

    hull = _empty(rig, 'CTRL_Hull', (0, 0, 0), 0.06, 'CUBE')
    _keep_parent(hull, root)
    bpy.context.view_layer.update()
    hull['note'] = 'Move along local Y to drive; wheels/tracks react'
    hull['travel'] = 0.0

    def world_pos(x, y, z):
        v = Matrix.Rotation(yaw, 4, 'Z') @ Vector((x * scale, y * scale, z * scale))
        return v

    # ------------------------------------------------------- turret / gun
    turret = _empty(rig, 'CTRL_Turret', world_pos(-0.10, 0.0, 1.345),
                    0.045, 'CIRCLE')
    _keep_parent(turret, hull)
    turret['control'] = 'turret_yaw_Z'
    _limit_rot(turret, x=(0, 0), y=(0, 0), z=(-120, 120))
    _label(rig, 'TURRET Z', world_pos(-0.10, 0.0, 1.50) + Vector((0, 0, 0.05)))
    bpy.context.view_layer.update()

    gun = _empty(rig, 'CTRL_Gun', world_pos(2.05, 0.0, 1.835), 0.04, 'SINGLE_ARROW')
    _keep_parent(gun, turret)
    gun.rotation_euler[2] = math.radians(-90)   # +X then pitches the barrel up
    gun['control'] = 'gun_pitch_X'
    _limit_rot(gun, x=(-10, 15), y=(0, 0), z=None)
    _label(rig, 'GUN X -10..15', world_pos(2.05, 0.0, 1.98) + Vector((0, 0, 0.04)))
    bpy.context.view_layer.update()

    def is_gun(name):
        return (name.startswith(('gun_', 'mantlet')) or
                name in ('mrs', 'mrs_mount'))

    def is_turret(name):
        if is_gun(name):
            return False
        return name.startswith(TURRET_PREFIXES)

    gun_parts = [o for o in objs if is_gun(o.name)]
    turret_parts = [o for o in objs if is_turret(o.name)]
    for o in gun_parts:
        _keep_parent(o, gun)
    for o in turret_parts:
        _keep_parent(o, turret)
    used.update(o.name for o in gun_parts)
    used.update(o.name for o in turret_parts)

    # ------------------------------------------------------- wheels
    wheel_x = [-2.58, -1.72, -0.86, 0.0, 0.86, 1.72, 2.58]
    wheel_pivots = []
    wheel_groups = {}
    for side in (0, 1):
        cy = -1.36 if side == 0 else 1.36
        for i, wx in enumerate(wheel_x):
            p = _empty(rig, f'CTRL_Wheel_{side}_{i}',
                       world_pos(wx, cy, 0.375), 0.018, 'SPHERE')
            _keep_parent(p, hull)
            p['control'] = 'wheel_roll_Y'
            wheel_groups[p.name] = []
            wheel_pivots.append(p)
    # classify wheel parts by name
    idler_pivots, sprocket_pivots = {}, {}
    for side in (0, 1):
        cy = -1.36 if side == 0 else 1.36
        p = _empty(rig, f'CTRL_Idler_{side}', world_pos(3.24, cy, 0.40),
                   0.02, 'SPHERE')
        _keep_parent(p, hull)
        p['control'] = 'idler_roll_Y'
        _wheel_driver(p, hull, 0.305 * scale)
        idler_pivots[side] = p
        wheel_pivots.append(p)
        p2 = _empty(rig, f'CTRL_Sprocket_{side}', world_pos(-3.24, cy, 0.40),
                    0.02, 'SPHERE')
        _keep_parent(p2, hull)
        p2['control'] = 'sprocket_roll_Y'
        _wheel_driver(p2, hull, 0.30 * scale)
        sprocket_pivots[side] = p2
        wheel_pivots.append(p2)
    bpy.context.view_layer.update()

    rx = re.compile(r'^(tire|rim|rimin|hub)_(\d)_(\d+)_')
    for o in objs:
        m = rx.match(o.name)
        if m:
            pname = f'CTRL_Wheel_{m.group(2)}_{m.group(3)}'
            if pname in wheel_groups:
                _keep_parent(o, bpy.data.objects[pname])
                wheel_groups[pname].append(o)
                used.add(o.name)
        elif o.name.startswith(IDLER_PREFIXES):
            side = 0 if re.search(r'[_-]0(?:_|$)', o.name) else 1
            _keep_parent(o, idler_pivots[side])
            used.add(o.name)
        elif o.name.startswith(SPROCKET_PREFIXES):
            side = 0 if re.search(r'[_-]0(?:_|$)', o.name) else 1
            _keep_parent(o, sprocket_pivots[side])
            used.add(o.name)

    # wheel drivers (radius 0.305 and 0.30) for the road wheels
    for p in wheel_pivots:
        if p.name.startswith(('CTRL_Wheel',)):
            _wheel_driver(p, hull, 0.305 * scale)

    # ------------------------------------------------------- tracks
    tracks = [o for o in objs if o.name.startswith('Track_')]
    track_root = _empty(rig, 'CTRL_TrackScroll', (0, 0, 0), 0.03, 'ARROWS')
    _keep_parent(track_root, hull)
    track_root['note'] = 'Track rig; curves are parented to the hull'
    for o in tracks:
        _keep_parent(o, track_root)
        used.add(o.name)

    # remaining meshes are the static hull
    for o in objs:
        if o.name not in used:
            _keep_parent(o, hull)

    # ------------------------------------------------------- visibility
    turret.hide_render = True
    gun.hide_render = True
    root.hide_render = True
    hull.hide_render = True
    track_root.hide_render = True
    for p in wheel_pivots:
        p.hide_render = True

    return {
        'root': root, 'hull': hull, 'turret': turret, 'gun': gun,
        'tracks': tracks, 'wheel_pivots': wheel_pivots,
        'wheel_groups': wheel_groups,
    }


def parent_world_to_scene_root(scene_root_name='SCENE_ROOT'):
    """Turn the whole diorama +90 deg about Z so the tank faces +Y.

    Camera/lights rotate with the scene, so the composition is unchanged.
    """
    sc = bpy.context.scene
    root = bpy.data.objects.new(scene_root_name, None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.3
    sc.collection.objects.link(root)
    top = [o for o in list(sc.objects) if o.parent is None and o is not root]
    for ob in top:
        mw = ob.matrix_basis.copy()
        ob.parent = root
        ob.matrix_world = mw
    root.rotation_euler[2] = math.radians(90)
    bpy.context.view_layer.update()
    return root
