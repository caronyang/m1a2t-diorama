"""Bake the scene to textures and export a GLB for the 360 web viewer.

Run after build/main.py has produced m1a2t_diorama.blend.
"""
import bpy
import bmesh
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLEND = os.path.join(ROOT, 'm1a2t_diorama.blend')
OUT = os.path.join(ROOT, 'web', 'scene.glb')

FAST = '--fast' in sys.argv


def select_only(obs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.hide_set(False)
        o.hide_viewport = False
        o.hide_render = False
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (obs[0] if obs else None)


def join(objs, name):
    objs = [o for o in objs if o.type == 'MESH']
    if not objs:
        return None
    if len(objs) == 1:
        objs[0].name = name
        return objs[0]
    select_only(objs, objs[0])
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def convert_texts():
    for o in list(bpy.data.objects):
        if o.type == 'FONT':
            bpy.context.view_layer.objects.active = o
            o.select_set(True)
            bpy.ops.object.convert(target='MESH')


def smart_uv(ob, margin=0.008):
    select_only([ob], ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    if FAST:
        bpy.ops.uv.smart_project(angle_limit=math.radians(75), island_margin=margin)
    else:
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')


def bake_color(ob, size, name, rough=0.7, metal=0.0):
    print('  UV', name)
    smart_uv(ob)
    img = bpy.data.images.new(name + '_albedo', size, size, alpha=False)
    img.colorspace_settings.name = 'sRGB'
    # add an active image node to every material slot
    for slot in ob.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        node = nt.nodes.new('ShaderNodeTexImage')
        node.image = img
        node.location = (-1200, 900)
        nt.nodes.active = node
        node.select = True
        for n in nt.nodes:
            if n is not node:
                n.select = False
    select_only([ob], ob)
    print('  bake', name, size)
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'},
                        margin=6, use_clear=True)
    # replace with the baked material
    mat = bpy.data.materials.new('MAT_' + name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0
    img.pack()
    return mat


def simple_mat(name, color, rough=0.7, metal=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (*color[:3], 1.0)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


def vertex_green(ob, name, base=(0.06, 0.12, 0.035), var=0.55):
    """Per-face green variation via vertex colours (no bake required)."""
    import random
    me = ob.data
    ca = me.color_attributes.new(name='Col', type='FLOAT_COLOR', domain='CORNER')
    ca = me.color_attributes['Col']
    rnd = random.Random(88)
    for p in me.polygons:
        v = 1.0 - var * 0.5 + rnd.random() * var
        for li in p.loop_indices:
            ca.data[li].color = (base[0] * v, base[1] * v, base[2] * v, 1.0)
    mat = bpy.data.materials.new('MAT_' + name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = 'Col'
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0


def foliage_mat(name, color, rough=0.85):
    ob = bpy.data.objects.get(name)
    if ob is None:
        return
    ob.data.materials.clear()
    ob.data.materials.append(simple_mat('MAT_' + name, color, rough, 0.0))
    for p in ob.data.polygons:
        p.material_index = 0


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'GPU'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type in ('OPTIX', 'CUDA')
    except Exception as e:
        print('gpu', e)
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.use_pass_color = True

    convert_texts()

    # ---------------------------------------------------------------- remove non-export
    for o in list(bpy.data.objects):
        n = o.name
        if (n.startswith('LightShaft') or n.startswith('ForestFog') or
                n.startswith('LBL_') or n in (
                    'BeautyCam', 'DioramaCam', 'Focus', 'SunKey', 'SunShaft',
                    'CanopySun', 'Key', 'Rim', 'SkyFill', 'Bounce') or
                o.type in ('LIGHT', 'CAMERA')):
            bpy.data.objects.remove(o, do_unlink=True)

    # ---------------------------------------------------------------- join groups
    coll = bpy.data.collections
    tank_coll = coll.get('TANK')

    def direct_meshes(parent):
        return [o for o in sc.objects if o.parent == parent and o.type == 'MESH']

    hull_ctrl = bpy.data.objects.get('CTRL_Hull')
    turret_ctrl = bpy.data.objects.get('CTRL_Turret')
    gun_ctrl = bpy.data.objects.get('CTRL_Gun')

    groups = {}
    groups['Hull'] = join(direct_meshes(hull_ctrl), 'Hull_Geo')
    groups['Turret'] = join(direct_meshes(turret_ctrl), 'Turret_Geo')
    groups['Gun'] = join(direct_meshes(gun_ctrl), 'Gun_Geo')

    # wheels: keep per-pivot, simple materials
    for o in list(sc.objects):
        if o.name.startswith(('CTRL_Wheel', 'CTRL_Idler', 'CTRL_Sprocket')):
            for ch in list(o.children):
                if ch.type == 'MESH':
                    nm = ch.name
                    if nm.startswith(('tire', 'Track')):
                        ch.data.materials.clear()
                        ch.data.materials.append(simple_mat('W_rubber', (0.012, 0.012, 0.011), 0.9))
                    elif nm.startswith(('rimin', 'hub', 'idlerh', 'sprocketh')):
                        ch.data.materials.clear()
                        ch.data.materials.append(simple_mat('W_steel', (0.08, 0.075, 0.06), 0.45, 0.7))
                    else:
                        ch.data.materials.clear()
                        ch.data.materials.append(simple_mat('W_olive', (0.055, 0.07, 0.032), 0.75, 0.05))

    # environment groups
    def env_meshes(prefixes, exclude=()):
        return [o for o in sc.objects if o.type == 'MESH' and
                o.parent is bpy.data.objects.get('SCENE_ROOT') and
                any(o.name.startswith(p) for p in prefixes) and
                not any(o.name.startswith(e) for e in exclude)]

    env = {}
    env['Terrain'] = join(env_meshes(['Terrain', 'DioramaSoil']), 'Terrain_Geo')
    env['Trunks'] = join(env_meshes(['PineTrunk', 'Stump']), 'Trunks_Geo')
    env['Needles'] = join(env_meshes(['PineNeedles']), 'Needles_Geo')
    env['Rocks'] = join(env_meshes(['Rock_', 'LogMoss']), 'Rocks_Geo')
    env['Ferns'] = join(env_meshes(['Fern_', 'Grass_']), 'Ferns_Geo')
    env['Details'] = join(env_meshes(['NeedleLitter', 'LeafLitter', 'RoadStones',
                                      'Twigs', 'Cone_', 'Log']), 'Details_Geo')
    env['Base'] = join(env_meshes(['Plinth', 'Plaque', 'PlaqueText', 'Foot']),
                       'Base_Geo')
    env['Water'] = join(env_meshes(['Puddle_', 'RutWater_']), 'Water_Geo')

    def decimate_obj(ob, ratio):
        if ob is None:
            return
        mod = ob.modifiers.new('WebDecimate', 'DECIMATE')
        mod.ratio = ratio
        select_only([ob], ob)
        bpy.ops.object.modifier_apply(modifier=mod.name)

    decimate_obj(env['Needles'], 1.0)
    decimate_obj(env['Ferns'], 0.55)
    decimate_obj(env['Terrain'], 0.65)
    decimate_obj(env['Details'], 0.85)

    # drop tracks (the viewer builds animated track links)
    for o in list(sc.objects):
        if o.name.startswith('Track_') or o.name.startswith('CTRL_TrackScroll'):
            if o.type == 'MESH':
                bpy.data.objects.remove(o, do_unlink=True)

    # ---------------------------------------------------------------- bake
    size = 1024 if FAST else 2048
    def maybe(ob, sz, nm, rough, metal=0.0):
        if ob is not None:
            bake_color(ob, sz, nm, rough, metal)
    maybe(groups['Hull'], size, 'Hull', 0.72, 0.05)
    maybe(groups['Turret'], size, 'Turret', 0.72, 0.05)
    maybe(groups['Gun'], size, 'Gun', 0.55, 0.25)
    maybe(env['Terrain'], size, 'Terrain', 0.9, 0.0)
    maybe(env['Trunks'], 1024 if not FAST else 512, 'Trunks', 0.85, 0.0)
    maybe(env['Rocks'], 1024 if not FAST else 512, 'Rocks', 0.85, 0.0)
    maybe(env['Details'], 1024 if not FAST else 512, 'Details', 0.85, 0.0)
    maybe(env['Base'], 1024 if not FAST else 512, 'Base', 0.4, 0.0)
    if env['Needles'] is not None:
        # keep the alpha-card material and its pine_bough texture
        pass
    if env['Ferns'] is not None:
        env['Ferns'].data.materials.clear()
        env['Ferns'].data.materials.append(
            simple_mat('MAT_Ferns', (0.08, 0.16, 0.05), 0.8))
    if env['Water']:
        env['Water'].data.materials.clear()
        env['Water'].data.materials.append(
            simple_mat('Water', (0.02, 0.016, 0.012), 0.05, 0.0))

    # ---------------------------------------------------------------- export
    # empties must not be filtered out as "hidden"
    for o in list(bpy.data.objects):
        if o.type == 'EMPTY':
            o.hide_render = False
            o.hide_viewport = False
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUT,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_yup=True,
        export_cameras=False,
        export_lights=False,
        export_extras=True,
        export_image_format='WEBP',
        export_image_quality=92,
        export_texcoords=True,
        export_normals=True,
        export_tangents=False,
        export_materials='EXPORT',
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_draco_position_quantization=14,
        export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12,
    )
    print('EXPORTED', OUT, os.path.getsize(OUT) / 1e6, 'MB')


if __name__ == '__main__':
    main()
