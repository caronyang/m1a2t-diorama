"""Build the M1A2T miniature diorama, render previews and save the .blend."""
import bpy
import bmesh
import math
import os
import sys
import random
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.append(HERE)

import utils
import mats
import tank
import env
import rig
from utils import clean_scene, collection, add_box, add_cyl, look_at, srgb, mesh_object

SCALE = 1.0 / 35.0
QUICK = '--quick' in sys.argv
NO_RENDER = '--norender' in sys.argv
NO_VOLUME = '--novolume' in sys.argv


def setup_render(sc):
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'GPU'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type in ('OPTIX', 'CUDA')
    except Exception as e:
        print('device setup:', e)
    sc.cycles.samples = 40 if QUICK else 160
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03 if QUICK else 0.012
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.max_bounces = 8
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 4
    sc.cycles.volume_bounces = 2
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.sample_clamp_indirect = 4.0
    sc.cycles.volume_step_rate = 2.0
    sc.cycles.volume_max_steps = 512
    sc.render.resolution_x = 1000 if QUICK else 1800
    sc.render.resolution_y = 667 if QUICK else 1200
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.use_persistent_data = True
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        try:
            sc.view_settings.look = 'AgX - Punchy'
        except Exception:
            pass
    sc.view_settings.exposure = 0.0


def scale_scene(s):
    objs = [o for o in bpy.data.objects]
    for ob in objs:
        if ob.type == 'MESH':
            ob.data.transform(Matrix.Scale(s, 4))
            ob.data.update()
        elif ob.type == 'EMPTY':
            ob.location = ob.location * s
            ob.scale = ob.scale * s
        elif ob.type in ('CAMERA', 'LIGHT'):
            ob.location = ob.location * s
            if ob.type == 'CAMERA':
                ob.data.dof.aperture_fstop = 7.1
            else:
                if ob.data.type == 'AREA':
                    ob.data.size *= s
                ob.data.energy *= 1.0


def build_base(M):
    bcoll = collection('BASE')
    terrain_w, terrain_d = 30.0 * SCALE, 22.0 * SCALE
    w, d = terrain_w + 0.055, terrain_d + 0.055
    top = -1.55 * SCALE
    h = 0.038
    base = add_box('Plinth', (0, 0, top - h / 2), (w, d, h), M['wood'], bcoll,
                   bevel=0.004)
    # small foot / shadow gap
    add_box('PlinthFoot', (0, 0, top - h - 0.004), (w * 0.95, d * 0.95, 0.008),
            M['black'], bcoll, bevel=0.003)
    # brass-framed dark nameplate with large gold lettering
    plaque_w = w * 0.52
    plaque_h = h * 0.82
    px, py, pz = 0.0, -d / 2, top - h * 0.53
    add_box('PlaqueBack', (px, py - 0.0015, pz),
            (plaque_w, 0.003, plaque_h), M['brass'], bcoll, bevel=0.0015)
    add_box('PlaqueInset', (px, py - 0.0030, pz),
            (plaque_w * 0.94, 0.002, plaque_h * 0.78),
            M['plaque_plate'], bcoll, bevel=0.0008)
    # engraved text
    cur = bpy.data.curves.new('PlaqueTextCurve', 'FONT')
    cur.body = 'M1A2T ABRAMS  ·  1:35'
    cur.size = plaque_h * 0.56
    cur.align_x = 'CENTER'
    cur.align_y = 'CENTER'
    cur.extrude = 0.0005
    txt = bpy.data.objects.new('PlaqueText', cur)
    txt.location = (px, py - 0.0042, pz - 0.0004)
    txt.rotation_euler = (math.radians(90), 0, 0)
    txt.data.materials.append(M['plaque_text'])
    bcoll.objects.link(txt)
    # corner brass feet
    for sx in (-1, 1):
        for sy in (-1, 1):
            add_cyl('Foot', (sx * (w / 2 - 0.018), sy * (d / 2 - 0.018),
                             top - h - 0.012), 0.012, 0.016, M['brass'], bcoll,
                    segs=12)
    return base


def build_lighting(sc):
    # world: cool forest daylight
    world = bpy.data.worlds.new('ForestWorld')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.20, 0.28, 0.35, 1.0)
    bg.inputs['Strength'].default_value = 0.42
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    # subtle sky gradient
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.05, 0.065, 0.055, 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (0.32, 0.44, 0.55, 1)
    nt.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])

    # sun key light, back-left
    ld = bpy.data.lights.new('SunKey', 'SUN')
    ld.energy = 8.5
    ld.angle = math.radians(0.9)
    ld.color = (1.0, 0.90, 0.74)
    sun = bpy.data.objects.new('SunKey', ld)
    sc.collection.objects.link(sun)
    direction = Vector((0.60, -0.44, -0.42)).normalized()
    sun.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    # cool skylight fill from camera side
    ad = bpy.data.lights.new('SkyFill', 'AREA')
    ad.energy = 40.0
    ad.size = 1.0
    ad.color = (0.72, 0.83, 1.0)
    fill = bpy.data.objects.new('SkyFill', ad)
    sc.collection.objects.link(fill)
    fill.location = (0.95, -1.05, 1.05)
    look_at(fill, (0, 0, 0.08))

    # warm bounce under the canopy
    ad2 = bpy.data.lights.new('Bounce', 'AREA')
    ad2.energy = 12.0
    ad2.size = 0.6
    ad2.color = (1.0, 0.82, 0.6)
    bounce = bpy.data.objects.new('Bounce', ad2)
    sc.collection.objects.link(bounce)
    bounce.location = (-0.9, 0.4, 0.55)
    look_at(bounce, (0, 0, 0.06))

    # warm canopy-gap shaft
    sd = bpy.data.lights.new('SunShaft', 'SPOT')
    sd.energy = 60.0
    sd.spot_size = math.radians(24)
    sd.spot_blend = 0.75
    sd.color = (1.0, 0.86, 0.62)
    shaft = bpy.data.objects.new('SunShaft', sd)
    sc.collection.objects.link(shaft)
    shaft.location = (-0.55, 0.85, 1.55)
    look_at(shaft, (0.02, 0.0, 0.06))

    # extra sun through a canopy gap, linked only to tank / ground / props
    recv = collection('SUN_RECEIVERS')
    for cname in ('TANK', 'TERRAIN', 'DETAILS', 'BASE'):
        c = bpy.data.collections.get(cname)
        if c:
            for ob in c.objects:
                if ob.name not in recv.objects:
                    recv.objects.link(ob)
    cld = bpy.data.lights.new('CanopySun', 'SUN')
    cld.energy = 5.0
    cld.angle = math.radians(3.0)
    cld.color = (1.0, 0.87, 0.68)
    csun = bpy.data.objects.new('CanopySun', cld)
    sc.collection.objects.link(csun)
    try:
        csun.light_linking.receiver_collection = recv
    except Exception as e:
        print('light linking:', e)
    cdir = Vector((-0.45, 0.50, -0.74)).normalized()
    csun.rotation_euler = cdir.to_track_quat('-Z', 'Y').to_euler()

    # soft key from camera-left to sculpt the tank
    kd = bpy.data.lights.new('Key', 'AREA')
    kd.energy = 7.0
    kd.size = 0.18
    kd.color = (1.0, 0.93, 0.82)
    key = bpy.data.objects.new('Key', kd)
    sc.collection.objects.link(key)
    key.location = (0.35, -0.58, 0.50)
    look_at(key, (0, 0, 0.08))

    # cool rim from behind to separate the silhouette
    rd = bpy.data.lights.new('Rim', 'AREA')
    rd.energy = 14.0
    rd.size = 0.45
    rd.color = (0.78, 0.88, 1.0)
    rim = bpy.data.objects.new('Rim', rd)
    sc.collection.objects.link(rim)
    rim.location = (-0.45, 0.35, 0.42)
    look_at(rim, (0, 0, 0.10))
    return sun


def build_fog(sc, M):
    fcoll = collection('ATMOSPHERE')
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.26))
    fog = bpy.context.object
    fog.name = 'ForestFog'
    fog.scale = (1.15, 0.95, 0.52)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for c in fog.users_collection:
        c.objects.unlink(fog)
    fcoll.objects.link(fog)
    m = bpy.data.materials.new('M_fog')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    vol = nt.nodes.new('ShaderNodeVolumePrincipled')
    vol.location = (300, 0)
    nt.links.new(vol.outputs['Volume'], out.inputs['Volume'])
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs['Vector'])
    # height falloff (generated z is 0..1 over the box)
    hr = nt.nodes.new('ShaderNodeMapRange')
    hr.location = (-250, -150)
    hr.inputs['From Min'].default_value = 0.0
    hr.inputs['From Max'].default_value = 0.75
    hr.inputs['To Min'].default_value = 1.0
    hr.inputs['To Max'].default_value = 0.035
    nt.links.new(sep.outputs['Z'], hr.inputs['Value'])
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.location = (-500, 150)
    n.inputs['Scale'].default_value = 4.0
    n.inputs['Detail'].default_value = 6.0
    n.inputs['Roughness'].default_value = 0.6
    n.inputs['Distortion'].default_value = 0.4
    nt.links.new(tc.outputs['Generated'], n.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.location = (-250, 150)
    mr.inputs['From Min'].default_value = 0.35
    mr.inputs['From Max'].default_value = 0.75
    mr.inputs['To Min'].default_value = 0.25
    mr.inputs['To Max'].default_value = 1.2
    nt.links.new(n.outputs['Fac'], mr.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.location = (0, 100)
    nt.links.new(mr.outputs['Result'], mul.inputs[0])
    nt.links.new(hr.outputs['Result'], mul.inputs[1])
    dens = nt.nodes.new('ShaderNodeMath')
    dens.operation = 'MULTIPLY'
    dens.location = (180, 100)
    dens.inputs[1].default_value = 0.07
    nt.links.new(mul.outputs['Value'], dens.inputs[0])
    nt.links.new(dens.outputs['Value'], vol.inputs['Density'])
    vol.inputs['Anisotropy'].default_value = 0.45
    vol.inputs['Color'].default_value = (0.78, 0.86, 0.95, 1.0)
    fog.data.materials.append(m)
    return fog


def build_shafts(sc, M):
    """Soft volumetric light shafts (subtle, render-only atmosphere)."""
    coll = collection('ATMOSPHERE')
    m = bpy.data.materials.new('M_shaft')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    vol = nt.nodes.new('ShaderNodeVolumePrincipled')
    vol.location = (350, 0)
    nt.links.new(vol.outputs['Volume'], out.inputs['Volume'])
    vol.inputs['Color'].default_value = (1.0, 0.88, 0.68, 1.0)
    vol.inputs['Anisotropy'].default_value = 0.55
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs['Vector'])
    # radial falloff inside the cylinder
    dx = nt.nodes.new('ShaderNodeMath'); dx.operation = 'SUBTRACT'
    dx.inputs[1].default_value = 0.5
    nt.links.new(sep.outputs['X'], dx.inputs[0])
    dy = nt.nodes.new('ShaderNodeMath'); dy.operation = 'SUBTRACT'
    dy.inputs[1].default_value = 0.5
    nt.links.new(sep.outputs['Y'], dy.inputs[0])
    xx = nt.nodes.new('ShaderNodeMath'); xx.operation = 'MULTIPLY'
    nt.links.new(dx.outputs[0], xx.inputs[0]); nt.links.new(dx.outputs[0], xx.inputs[1])
    yy = nt.nodes.new('ShaderNodeMath'); yy.operation = 'MULTIPLY'
    nt.links.new(dy.outputs[0], yy.inputs[0]); nt.links.new(dy.outputs[0], yy.inputs[1])
    rr = nt.nodes.new('ShaderNodeMath'); rr.operation = 'ADD'
    nt.links.new(xx.outputs[0], rr.inputs[0]); nt.links.new(yy.outputs[0], rr.inputs[1])
    rr2 = nt.nodes.new('ShaderNodeMath'); rr2.operation = 'SQRT'
    nt.links.new(rr.outputs[0], rr2.inputs[0])
    rad = nt.nodes.new('ShaderNodeMapRange')
    rad.inputs['From Min'].default_value = 1.0
    rad.inputs['From Max'].default_value = 0.12
    rad.inputs['To Min'].default_value = 0.0
    rad.inputs['To Max'].default_value = 1.0
    nt.links.new(rr2.outputs[0], rad.inputs['Value'])
    # length falloff
    zf = nt.nodes.new('ShaderNodeMapRange')
    zf.inputs['From Min'].default_value = 0.0
    zf.inputs['From Max'].default_value = 0.22
    zf.inputs['To Min'].default_value = 0.0
    zf.inputs['To Max'].default_value = 1.0
    nt.links.new(sep.outputs['Z'], zf.inputs['Value'])
    zf2 = nt.nodes.new('ShaderNodeMapRange')
    zf2.inputs['From Min'].default_value = 1.0
    zf2.inputs['From Max'].default_value = 0.80
    zf2.inputs['To Min'].default_value = 0.0
    zf2.inputs['To Max'].default_value = 1.0
    nt.links.new(sep.outputs['Z'], zf2.inputs['Value'])
    zm = nt.nodes.new('ShaderNodeMath'); zm.operation = 'MULTIPLY'
    nt.links.new(zf.outputs['Result'], zm.inputs[0])
    nt.links.new(zf2.outputs['Result'], zm.inputs[1])
    # noise variation
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = 3.0
    n.inputs['Detail'].default_value = 4.0
    n.inputs['Roughness'].default_value = 0.6
    nt.links.new(tc.outputs['Object'], n.inputs['Vector'])
    nm = nt.nodes.new('ShaderNodeMapRange')
    nm.inputs['From Min'].default_value = 0.3
    nm.inputs['From Max'].default_value = 0.7
    nm.inputs['To Min'].default_value = 0.35
    nm.inputs['To Max'].default_value = 1.0
    nt.links.new(n.outputs['Fac'], nm.inputs['Value'])
    m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'
    nt.links.new(rad.outputs['Result'], m1.inputs[0])
    nt.links.new(zm.outputs['Value'], m1.inputs[1])
    m2 = nt.nodes.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'
    nt.links.new(m1.outputs['Value'], m2.inputs[0])
    nt.links.new(nm.outputs['Result'], m2.inputs[1])
    dens = nt.nodes.new('ShaderNodeMath'); dens.operation = 'MULTIPLY'
    dens.inputs[1].default_value = 0.9
    nt.links.new(m2.outputs['Value'], dens.inputs[0])
    nt.links.new(dens.outputs['Value'], vol.inputs['Density'])
    # gentle self-glow so the shafts read through the haze
    em = nt.nodes.new('ShaderNodeMath'); em.operation = 'MULTIPLY'
    em.inputs[1].default_value = 1.0
    nt.links.new(m2.outputs['Value'], em.inputs[0])
    nt.links.new(em.outputs['Value'], vol.inputs['Emission Strength'])
    vol.inputs['Emission Color'].default_value = (1.0, 0.86, 0.62, 1.0)

    direction = Vector((0.60, -0.44, -0.42)).normalized()
    rot = direction.to_track_quat('Z', 'Y').to_euler()
    for i, (pos, radius, length) in enumerate([
            ((-0.22, 0.25, 0.18), 0.060, 0.85),
            ((0.00, 0.12, 0.24), 0.085, 0.70),
            ((-0.46, 0.03, 0.13), 0.035, 0.60),
            ((0.17, 0.36, 0.20), 0.045, 0.75),
            ((-0.10, 0.46, 0.16), 0.030, 0.55)]):
        ob = add_cyl(f'LightShaft_{i}', (0, 0, 0), radius, length, m, coll,
                     segs=20, smooth=True)
        ob.location = Vector(pos)
        ob.rotation_euler = rot
    return coll


def build_camera(sc):
    cd = bpy.data.cameras.new('BeautyCam')
    cd.lens = 80.0
    cd.sensor_width = 36.0
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = 6.3
    cd.dof.aperture_blades = 7
    cd.dof.aperture_rotation = math.radians(12)
    cam = bpy.data.objects.new('BeautyCam', cd)
    sc.collection.objects.link(cam)
    cam.location = (0.545, -0.735, 0.295)
    look_at(cam, (0.0, 0.005, 0.070))
    focus = bpy.data.objects.new('Focus', None)
    sc.collection.objects.link(focus)
    focus.location = (0.03, 0.0, 0.06)
    cd.dof.focus_object = focus
    sc.camera = cam
    return cam


def build_compositor(sc):
    sc.use_nodes = True
    nt = sc.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers')
    glare = nt.nodes.new('CompositorNodeGlare')
    glare.glare_type = 'FOG_GLOW'
    glare.quality = 'HIGH'
    glare.threshold = 1.0
    glare.size = 7
    glare.mix = -0.25
    nt.links.new(rl.outputs['Image'], glare.inputs['Image'])
    hue = nt.nodes.new('CompositorNodeHueSat')
    hue.inputs['Saturation'].default_value = 1.18
    hue.inputs['Value'].default_value = 1.02
    nt.links.new(glare.outputs['Image'], hue.inputs['Image'])
    try:
        cb = nt.nodes.new('CompositorNodeColorBalance')
        cb.correction_method = 'LIFT_GAMMA_GAIN'
        cb.lift = (0.98, 1.0, 1.05, 1.0)
        cb.gain = (1.06, 1.02, 0.96, 1.0)
        nt.links.new(hue.outputs['Image'], cb.inputs['Image'])
        base_img = cb.outputs['Image']
    except Exception as e:
        print('color balance:', e)
        base_img = hue.outputs['Image']
    lens = nt.nodes.new('CompositorNodeLensdist')
    lens.inputs['Dispersion'].default_value = 0.008
    nt.links.new(base_img, lens.inputs['Image'])
    # vignette
    ell = nt.nodes.new('CompositorNodeEllipseMask')
    ell.width = 0.82
    ell.height = 0.95
    blur = nt.nodes.new('CompositorNodeBlur')
    blur.filter_type = 'FAST_GAUSS'
    blur.size_x = 260
    blur.size_y = 260
    nt.links.new(ell.outputs['Mask'], blur.inputs['Image'])
    mix = nt.nodes.new('CompositorNodeMixRGB')
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 0.55
    nt.links.new(lens.outputs['Image'], mix.inputs[1])
    nt.links.new(blur.outputs['Image'], mix.inputs[2])
    comp = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(mix.outputs[0], comp.inputs['Image'])


def main():
    clean_scene()
    sc = bpy.context.scene
    setup_render(sc)

    M = mats.build_materials()
    tank_coll = collection('TANK')
    camo = bpy.data.objects.new('CamoSpace', None)
    tank_coll.objects.link(camo)
    camo.location = (0, 0, 1.18)
    tank.build_tank(M, tank_coll, camo, yaw=math.radians(7.0))

    print('building forest ...')
    terrain, ter, soil, trunks, needles, ferns, puddles = env.build_forest(M)
    print('forest done')

    # scale down to 1:35
    scale_scene(SCALE)
    rig_info = rig.build_rig(tank_coll, math.radians(7.0), SCALE)
    build_base(M)
    sun = build_lighting(sc)
    if not NO_VOLUME:
        build_fog(sc, M)
        build_shafts(sc, M)
    cam = build_camera(sc)
    build_compositor(sc)
    setup_render(sc)

    # duplicate a wide "diorama" camera for documentation
    cd = bpy.data.cameras.new('DioramaCam')
    cd.lens = 80.0
    cd.dof.use_dof = False
    cam2 = bpy.data.objects.new('DioramaCam', cd)
    sc.collection.objects.link(cam2)
    cam2.location = (1.15, -1.15, 0.82)
    look_at(cam2, (0, 0, 0.045))

    # Finally rotate the whole world +90 about Z: the tank now faces +Y while
    # the camera / lights turn with it, so the composition is unchanged.
    scene_root = rig.parent_world_to_scene_root()

    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print('pack:', e)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'm1a2t_diorama.blend'))
    print('saved blend')

    if NO_RENDER:
        return
    sc.camera = cam
    sc.render.filepath = os.path.join(ROOT, 'renders', 'preview.png')
    bpy.ops.render.render(write_still=True)
    print('render done')


if __name__ == '__main__':
    main()
