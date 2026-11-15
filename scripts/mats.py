"""Procedural materials for the M1A2T forest diorama."""
import bpy
import os
from utils import srgb, base_material, add_noise_bump

TEXDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textures')


def _img(nt, fname, vector, scale=(1, 1, 1), loc=(0, 0), noncolor=False,
         rough=False):
    img = bpy.data.images.load(os.path.join(TEXDIR, fname), check_existing=True)
    if noncolor:
        img.colorspace_settings.name = 'Non-Color'
    node = nt.nodes.new('ShaderNodeTexImage')
    node.image = img
    node.projection = 'BOX'
    node.projection_blend = 0.35
    node.location = loc
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.location = (loc[0] - 200, loc[1])
    mp.inputs['Scale'].default_value = scale
    nt.links.new(vector, mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], node.inputs['Vector'])
    return node


def _math(nt, op, a=None, b=None, loc=(0, 0)):
    n = nt.nodes.new('ShaderNodeMath')
    n.operation = op
    n.location = loc
    if a is not None:
        n.inputs[0].default_value = a
    if b is not None:
        n.inputs[1].default_value = b
    return n


def _noise(nt, vec, scale, detail=4.0, rough=0.5, distortion=0.0, loc=(0, 0)):
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.location = loc
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    n.inputs['Distortion'].default_value = distortion
    nt.links.new(vec, n.inputs['Vector'])
    return n


def _ramp(nt, fac, stops, loc=(0, 0), interp='CONSTANT'):
    r = nt.nodes.new('ShaderNodeValToRGB')
    r.location = loc
    r.color_ramp.interpolation = interp
    els = r.color_ramp.elements
    while len(els) > 2:
        els.remove(els[-1])
    for i, (pos, col) in enumerate(stops):
        if i < 2:
            e = els[i]
        else:
            e = els.new(pos)
        e.position = pos
        e.color = col
    return r


def _mix(nt, fac, c1, c2, blend='MIX', loc=(0, 0)):
    m = nt.nodes.new('ShaderNodeMixRGB')
    m.blend_type = blend
    m.location = loc
    m.inputs['Fac'].default_value = fac
    if isinstance(c1, tuple):
        m.inputs['Color1'].default_value = c1
    else:
        nt.links.new(c1, m.inputs['Color1'])
    if isinstance(c2, tuple):
        m.inputs['Color2'].default_value = c2
    else:
        nt.links.new(c2, m.inputs['Color2'])
    return m


def build_materials(camo_space=None):
    M = {}
    col = {}

    # ---------------------------------------------------------------- tank camo
    m = bpy.data.materials.new('M_TankCamo')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (900, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (650, 0)

    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1100, 100)
    if camo_space:
        tc.object = camo_space
    obj = tc.outputs['Object']
    mapn = nt.nodes.new('ShaderNodeMapping'); mapn.location = (-900, 100)
    mapn.inputs['Scale'].default_value = (1.0, 1.0, 1.0)
    nt.links.new(obj, mapn.inputs['Vector'])

    blotch = _noise(nt, mapn.outputs['Vector'], 1.55, detail=2.2, rough=0.5,
                    distortion=1.9, loc=(-700, 150))
    r = _ramp(nt, blotch.outputs['Fac'],
              [(0.00, srgb('6A7547')),        # light olive green
               (0.40, srgb('44512D')),        # forest green
               (0.545, srgb('171A11')),       # black blotch
               (0.64, srgb('4E3620')),        # earth brown
               (0.76, srgb('202B15'))], loc=(-450, 150))
    nt.links.new(blotch.outputs['Fac'], r.inputs['Fac'])

    # fine paint mottling
    fine = _noise(nt, mapn.outputs['Vector'], 26.0, detail=8.0, rough=0.62,
                  loc=(-700, -150))
    fr = _ramp(nt, fine.outputs['Fac'],
               [(0.25, (0.72, 0.72, 0.72, 1)), (0.75, (1.0, 1.0, 1.0, 1))],
               loc=(-450, -150), interp='LINEAR')
    nt.links.new(fine.outputs['Fac'], fr.inputs['Fac'])
    paint = _mix(nt, 0.55, r.outputs['Color'], fr.outputs['Color'], 'MULTIPLY',
                 loc=(-200, 100))
    nt.links.new(r.outputs['Color'], paint.inputs['Color1'])
    nt.links.new(fr.outputs['Color'], paint.inputs['Color2'])

    # dust / mud rising from the running gear
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-900, -400)
    nt.links.new(obj, sep.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.location = (-700, -400)
    mr.inputs['From Min'].default_value = -1.05
    mr.inputs['From Max'].default_value = -0.22
    mr.inputs['To Min'].default_value = 1.0
    mr.inputs['To Max'].default_value = 0.0
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    dustn = _noise(nt, mapn.outputs['Vector'], 3.2, detail=10.0, rough=0.7,
                   loc=(-700, -620))
    dmul = _math(nt, 'MULTIPLY', loc=(-450, -500))
    nt.links.new(mr.outputs['Result'], dmul.inputs[0])
    nt.links.new(dustn.outputs['Fac'], dmul.inputs[1])
    dmask = nt.nodes.new('ShaderNodeMapRange'); dmask.location = (-250, -500)
    dmask.inputs['From Min'].default_value = 0.18
    dmask.inputs['From Max'].default_value = 0.75
    dmask.inputs['To Min'].default_value = 0.0
    dmask.inputs['To Max'].default_value = 0.45
    nt.links.new(dmul.outputs['Value'], dmask.inputs['Value'])
    dusty = _mix(nt, 0.0, paint.outputs['Color'], srgb('5F4A30'), 'MIX',
                 loc=(50, 0))
    nt.links.new(dmask.outputs['Result'], dusty.inputs['Fac'])
    nt.links.new(paint.outputs['Color'], dusty.inputs['Color1'])

    # vertical grime streaks
    smap = nt.nodes.new('ShaderNodeMapping'); smap.location = (-900, -950)
    smap.inputs['Scale'].default_value = (6.0, 6.0, 0.35)
    nt.links.new(obj, smap.inputs['Vector'])
    sn = nt.nodes.new('ShaderNodeTexNoise'); sn.location = (-700, -950)
    sn.inputs['Scale'].default_value = 7.0
    sn.inputs['Detail'].default_value = 6.0
    sn.inputs['Roughness'].default_value = 0.65
    nt.links.new(smap.outputs['Vector'], sn.inputs['Vector'])
    sramp = nt.nodes.new('ShaderNodeMapRange'); sramp.location = (-450, -950)
    sramp.inputs['From Min'].default_value = 0.48
    sramp.inputs['From Max'].default_value = 0.72
    sramp.inputs['To Min'].default_value = 0.0
    sramp.inputs['To Max'].default_value = 0.30
    nt.links.new(sn.outputs['Fac'], sramp.inputs['Value'])
    grime = _mix(nt, 0.0, dusty.outputs['Color'], srgb('241A10'), 'MIX',
                 loc=(300, 0))
    nt.links.new(sramp.outputs['Result'], grime.inputs['Fac'])
    nt.links.new(dusty.outputs['Color'], grime.inputs['Color1'])

    nt.links.new(grime.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Metallic'].default_value = 0.05
    bsdf.inputs['Roughness'].default_value = 0.62
    nt.links.new(dmask.outputs['Result'], bsdf.inputs['Roughness'])
    # roughness override range
    rm = nt.nodes.new('ShaderNodeMapRange'); rm.location = (400, -200)
    rm.inputs['To Min'].default_value = 0.52
    rm.inputs['To Max'].default_value = 0.95
    nt.links.new(dmask.outputs['Result'], rm.inputs['Value'])
    nt.links.new(rm.outputs['Result'], bsdf.inputs['Roughness'])

    bumpn = _noise(nt, mapn.outputs['Vector'], 90.0, detail=10.0, rough=0.65,
                   loc=(50, -700))
    bump = nt.nodes.new('ShaderNodeBump'); bump.location = (400, -600)
    bump.inputs['Strength'].default_value = 0.32
    bump.inputs['Distance'].default_value = 0.003
    nt.links.new(bumpn.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['camo'] = m

    # ---------------------------------------------------------------- dark metal
    for name, hexcol, rough, metal in [
            ('metal', '2B2C28', 0.48, 0.75),
            ('metal_dark', '161714', 0.55, 0.6),
            ('rubber', '131412', 0.88, 0.0),
            ('paint_dark', '24291F', 0.65, 0.1)]:
        m, nt, bsdf = base_material('M_' + name, srgb(hexcol), rough, metal)
        add_noise_bump(nt, bsdf, scale=95.0, strength=0.22, coord='Object')
        M[name] = m

    # rusty track steel
    m = bpy.data.materials.new('M_track')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (700, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (450, 0)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-700, 0)
    n1 = _noise(nt, tc.outputs['Object'], 18.0, 8.0, 0.65, 0.3, loc=(-500, 100))
    rr = _ramp(nt, n1.outputs['Fac'],
               [(0.2, srgb('3B3A32')), (0.55, srgb('5A4A36')),
                (0.75, srgb('7A5A38')), (1.0, srgb('8A6A45'))], loc=(-260, 100),
               interp='LINEAR')
    nt.links.new(n1.outputs['Fac'], rr.inputs['Fac'])
    nt.links.new(rr.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Metallic'].default_value = 0.55
    bsdf.inputs['Roughness'].default_value = 0.62
    add_noise_bump(nt, bsdf, scale=160.0, strength=0.35, coord='Object',
                   loc=(-700, -500))
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['track'] = m

    # ---------------------------------------------------------------- optics
    m, nt, bsdf = base_material('M_lens', srgb('0B1414'), 0.06, 0.7, 0.8)
    bsdf.inputs['Coat Weight'].default_value = 1.0
    bsdf.inputs['Coat Roughness'].default_value = 0.03
    M['lens'] = m

    m, nt, bsdf = base_material('M_lightglass', srgb('C8C2A8'), 0.08, 0.2, 0.9)
    bsdf.inputs['Emission Color'].default_value = srgb('FFE9B8')
    bsdf.inputs['Emission Strength'].default_value = 0.35
    M['lamp'] = m

    M['yellow'] = base_material('M_yellow', srgb('C69A18'), 0.55, 0.0)[0]
    M['black'] = base_material('M_black', srgb('101110'), 0.7, 0.1)[0]
    M['brass'] = base_material('M_brass', srgb('B08B45'), 0.28, 1.0)[0]
    M['plaque_plate'] = base_material('M_plaque_plate', srgb('181510'), 0.38, 0.25)[0]
    mpt, ntpt, bpt = base_material('M_plaque_text', srgb('E6C47C'), 0.3, 0.55)
    bpt.inputs['Emission Color'].default_value = srgb('E6C47C')
    bpt.inputs['Emission Strength'].default_value = 0.35
    M['plaque_text'] = mpt
    M['red'] = base_material('M_red', srgb('6A1410'), 0.5, 0.2)[0]
    M['green_flag'] = base_material('M_greenflag', srgb('3E5A2A'), 0.7, 0.0)[0]

    # ---------------------------------------------------------------- wood base
    m = bpy.data.materials.new('M_wood')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (800, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (550, 0)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-700, 0)
    mp = nt.nodes.new('ShaderNodeMapping'); mp.location = (-520, 0)
    mp.inputs['Scale'].default_value = (1.0, 14.0, 1.0)
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
    wv = nt.nodes.new('ShaderNodeTexWave'); wv.location = (-320, 100)
    wv.wave_type = 'BANDS'
    wv.bands_direction = 'Y'
    wv.inputs['Scale'].default_value = 3.5
    wv.inputs['Distortion'].default_value = 8.0
    wv.inputs['Detail'].default_value = 4.0
    wv.inputs['Detail Scale'].default_value = 1.0
    nt.links.new(mp.outputs['Vector'], wv.inputs['Vector'])
    rr = _ramp(nt, wv.outputs['Fac'],
               [(0.0, srgb('2C1B10')), (0.35, srgb('4A2E19')),
                (0.6, srgb('38200F')), (0.8, srgb('55351D'))], loc=(100, 100),
               interp='LINEAR')
    nt.links.new(wv.outputs['Fac'], rr.inputs['Fac'])
    nt.links.new(rr.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.34
    bsdf.inputs['Coat Weight'].default_value = 0.35
    bsdf.inputs['Coat Roughness'].default_value = 0.18
    add_noise_bump(nt, bsdf, scale=60.0, strength=0.08, coord='Generated',
                   loc=(-700, -500))
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['wood'] = m

    # ---------------------------------------------------------------- rock
    m = bpy.data.materials.new('M_rock')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (900, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (650, 0)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1200, 100)
    tex = _img(nt, 'mossy_rock_diff_1k.jpg', tc.outputs['Generated'],
               (1.4, 1.4, 1.4), loc=(-950, 250))
    dark = _mix(nt, 0.6, tex.outputs['Color'], srgb('8A8270'), 'MULTIPLY',
                loc=(-500, 250))
    bsdf.inputs['Roughness'].default_value = 0.82
    # moss creeping on upward faces
    geo = nt.nodes.new('ShaderNodeNewGeometry'); geo.location = (-1000, -200)
    sepn = nt.nodes.new('ShaderNodeSeparateXYZ'); sepn.location = (-800, -200)
    nt.links.new(geo.outputs['Normal'], sepn.inputs['Vector'])
    upr = nt.nodes.new('ShaderNodeMapRange'); upr.location = (-600, -200)
    upr.inputs['From Min'].default_value = 0.05
    upr.inputs['From Max'].default_value = 0.75
    nt.links.new(sepn.outputs['Z'], upr.inputs['Value'])
    mn = _noise(nt, tc.outputs['Object'], 8.0, 10.0, 0.75, 0.0, loc=(-800, -450))
    mmul = _math(nt, 'MULTIPLY', loc=(-450, -300))
    nt.links.new(upr.outputs['Result'], mmul.inputs[0])
    nt.links.new(mn.outputs['Fac'], mmul.inputs[1])
    mramp = _ramp(nt, mmul.outputs['Value'],
                  [(0.42, (0, 0, 0, 1)), (0.62, (1, 1, 1, 1))],
                  loc=(-250, -300), interp='LINEAR')
    nt.links.new(mmul.outputs['Value'], mramp.inputs['Fac'])
    moss = _mix(nt, 1.0, dark.outputs['Color'], srgb('2A3A16'), 'MIX',
                loc=(0, 100))
    nt.links.new(mramp.outputs['Color'], moss.inputs['Fac'])
    nt.links.new(dark.outputs['Color'], moss.inputs['Color1'])
    nt.links.new(moss.outputs['Color'], bsdf.inputs['Base Color'])
    add_noise_bump(nt, bsdf, scale=22.0, strength=0.6, coord='Object',
                   loc=(-800, -750))
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['rock'] = m

    # ---------------------------------------------------------------- pine bark
    m = bpy.data.materials.new('M_bark')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (900, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (650, 0)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1000, 0)
    tex = _img(nt, 'bark_brown_02_diff_1k.jpg', tc.outputs['Generated'],
               (1.5, 1.5, 8.0), loc=(-750, 200))
    tint = _mix(nt, 0.6, tex.outputs['Color'], srgb('8A7A64'), 'MULTIPLY',
                loc=(-400, 200))
    nt.links.new(tex.outputs['Color'], tint.inputs['Color1'])
    nt.links.new(tint.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.88
    add_noise_bump(nt, bsdf, scale=35.0, strength=0.75, coord='Object',
                   loc=(-900, -500))
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['bark'] = m

    # ---------------------------------------------------------------- needles
    m = bpy.data.materials.new('M_pine')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (800, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (550, 0)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-900, 0)
    n1 = _noise(nt, tc.outputs['Object'], 14.0, 8.0, 0.7, 0.4, loc=(-700, 100))
    rr = _ramp(nt, n1.outputs['Fac'],
               [(0.1, srgb('263A1B')), (0.4, srgb('38501F')),
                (0.62, srgb('4A6128')), (0.82, srgb('5A6C32'))],
               loc=(-450, 100), interp='LINEAR')
    nt.links.new(n1.outputs['Fac'], rr.inputs['Fac'])
    nt.links.new(rr.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.72
    bsdf.inputs['Subsurface Weight'].default_value = 0.10
    bsdf.inputs['Subsurface Radius'].default_value = (0.0012, 0.0028, 0.0006)
    add_noise_bump(nt, bsdf, scale=260.0, strength=0.9, coord='Object',
                   loc=(-700, -400))
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['pine'] = m
    M['pine_core'] = base_material('M_pine_core', srgb('2B3D1D'), 0.82, 0.0)[0]

    # alpha-card pine bough (used by the foliage cards)
    m = bpy.data.materials.new('M_pine_card')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (700, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (450, 0)
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.location = (0, 100)
    tex.image = bpy.data.images.load(os.path.join(TEXDIR, 'pine_bough.png'),
                                     check_existing=True)
    tex.image.colorspace_settings.name = 'sRGB'
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 0.10
    bsdf.inputs['Roughness'].default_value = 0.82
    m.use_backface_culling = False
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        pass
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['pine_card'] = m

    # ---------------------------------------------------------------- fern / grass
    for name, hexa, hexb in [('fern', '243A14', '3A5520'),
                             ('grass', '3A4524', '5A5A30')]:
        m = bpy.data.materials.new('M_' + name)
        m.use_nodes = True
        nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (800, 0)
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (550, 0)
        tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-800, 0)
        n1 = _noise(nt, tc.outputs['Object'], 9.0, 6.0, 0.6, 0.3, loc=(-600, 100))
        rr = _ramp(nt, n1.outputs['Fac'],
                   [(0.2, srgb(hexa)), (0.75, srgb(hexb))],
                   loc=(-350, 100), interp='LINEAR')
        nt.links.new(n1.outputs['Fac'], rr.inputs['Fac'])
        nt.links.new(rr.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.55
        bsdf.inputs['Subsurface Weight'].default_value = 0.05
        bsdf.inputs['Subsurface Radius'].default_value = (0.0004, 0.0014, 0.0003)
        nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
        M[name] = m

    # ---------------------------------------------------------------- water
    m = bpy.data.materials.new('M_water')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (600, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (350, 0)
    bsdf.inputs['Base Color'].default_value = srgb('17110B')
    bsdf.inputs['Roughness'].default_value = 0.018
    bsdf.inputs['IOR'].default_value = 1.33
    bsdf.inputs['Metallic'].default_value = 0.0
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-600, -300)
    n1 = _noise(nt, tc.outputs['Generated'], 24.0, 4.0, 0.6, 0.3,
                loc=(-400, -300))
    bump = nt.nodes.new('ShaderNodeBump'); bump.location = (100, -300)
    bump.inputs['Strength'].default_value = 0.06
    bump.inputs['Distance'].default_value = 0.002
    nt.links.new(n1.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['water'] = m

    # ---------------------------------------------------------------- terrain
    m = bpy.data.materials.new('M_terrain')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (1200, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (950, 0)

    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1500, 0)
    att = nt.nodes.new('ShaderNodeAttribute'); att.location = (-1200, 300)
    att.attribute_name = 'Col'
    wet = nt.nodes.new('ShaderNodeAttribute'); wet.location = (-1200, 100)
    wet.attribute_name = 'Wet'
    road = nt.nodes.new('ShaderNodeAttribute'); road.location = (-1200, -100)
    road.attribute_name = 'Road'

    tex_floor = _img(nt, 'leaves_forest_ground_diff_1k.jpg',
                     tc.outputs['Generated'], (18.0, 14.0, 1.0),
                     loc=(-900, 350))
    tex_mud = _img(nt, 'muddy_tracks_diff_1k.jpg',
                   tc.outputs['Generated'], (22.0, 16.0, 1.0),
                   loc=(-900, 100))
    tex_gravel = _img(nt, 'forest_ground_04_diff_1k.jpg',
                      tc.outputs['Generated'], (24.0, 18.0, 1.0),
                      loc=(-900, -150))

    # road blend
    mix1 = _mix(nt, 0.0, tex_floor.outputs['Color'], tex_mud.outputs['Color'],
                'MIX', loc=(-500, 300))
    nt.links.new(road.outputs['Fac'], mix1.inputs['Fac'])
    # gravel showing through the mud
    gfac = nt.nodes.new('ShaderNodeMath'); gfac.operation = 'MULTIPLY'
    gfac.inputs[1].default_value = 0.10
    gfac.location = (-500, 0)
    nt.links.new(road.outputs['Fac'], gfac.inputs[0])
    mix2 = _mix(nt, 0.0, mix1.outputs['Color'], tex_gravel.outputs['Color'],
                'MIX', loc=(-250, 250))
    nt.links.new(gfac.outputs['Value'], mix2.inputs['Fac'])
    # darken to forest-floor exposure
    darken = _mix(nt, 0.86, mix2.outputs['Color'], srgb('7A684C'),
                  'MULTIPLY', loc=(0, 300))
    # moss creeping in from the verges
    mn = _noise(nt, tc.outputs['Generated'], 9.0, 6.0, 0.6, 0.3,
                loc=(-500, -300))
    mramp = _ramp(nt, mn.outputs['Fac'],
                  [(0.50, (0, 0, 0, 1)), (0.68, (1, 1, 1, 1))],
                  loc=(-250, -300), interp='LINEAR')
    nt.links.new(mn.outputs['Fac'], mramp.inputs['Fac'])
    moss_fac = nt.nodes.new('ShaderNodeMath'); moss_fac.operation = 'MULTIPLY'
    moss_fac.location = (0, -250)
    nt.links.new(mramp.outputs['Color'], moss_fac.inputs[0])
    nt.links.new(road.outputs['Fac'], moss_fac.inputs[1])
    mossfac2 = nt.nodes.new('ShaderNodeMapRange'); mossfac2.location = (180, -250)
    mossfac2.inputs['To Min'].default_value = 0.30
    mossfac2.inputs['To Max'].default_value = 0.0
    nt.links.new(moss_fac.outputs['Value'], mossfac2.inputs['Value'])
    mossc = _mix(nt, 0.0, darken.outputs['Color'], srgb('1E2A12'), 'MIX',
                 loc=(350, 250))
    nt.links.new(mossfac2.outputs['Result'], mossc.inputs['Fac'])
    # wet mud darkening
    wetmix = _mix(nt, 0.0, mossc.outputs['Color'], srgb('15100A'), 'MIX',
                  loc=(600, 250))
    nt.links.new(wet.outputs['Fac'], wetmix.inputs['Fac'])
    nt.links.new(wetmix.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.9
    rmap = nt.nodes.new('ShaderNodeMapRange'); rmap.location = (600, -100)
    rmap.inputs['To Min'].default_value = 0.88
    rmap.inputs['To Max'].default_value = 0.28
    nt.links.new(wet.outputs['Fac'], rmap.inputs['Value'])
    nt.links.new(rmap.outputs['Result'], bsdf.inputs['Roughness'])
    n_fine = _noise(nt, tc.outputs['Generated'], 900.0, 12.0, 0.7, 0.2,
                    loc=(300, -600))
    bump = nt.nodes.new('ShaderNodeBump'); bump.location = (750, -500)
    bump.inputs['Strength'].default_value = 0.45
    bump.inputs['Distance'].default_value = 0.004
    nt.links.new(n_fine.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['terrain'] = m

    # wet soil sides of the diorama
    m = bpy.data.materials.new('M_soil')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (800, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (550, 0)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-800, 0)
    n1 = _noise(nt, tc.outputs['Object'], 5.0, 10.0, 0.7, 0.4, loc=(-600, 100))
    rr = _ramp(nt, n1.outputs['Fac'],
               [(0.1, srgb('2E2115')), (0.4, srgb('4A3423')),
                (0.6, srgb('3A2A1B')), (0.8, srgb('5C4530'))],
               loc=(-350, 100), interp='LINEAR')
    nt.links.new(n1.outputs['Fac'], rr.inputs['Fac'])
    nt.links.new(rr.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.95
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['soil'] = m

    # dust / clods on the tank
    M['mud'] = base_material('M_mud', srgb('4E3823'), 0.95, 0.0)[0]
    M['stone'] = base_material('M_stone', srgb('3C3A33'), 0.8, 0.05)[0]

    # fallen leaves (per-vertex colours)
    m = bpy.data.materials.new('M_leaf')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (700, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (450, 0)
    att = nt.nodes.new('ShaderNodeAttribute'); att.location = (-200, 100)
    att.attribute_name = 'Col'
    nt.links.new(att.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.78
    add_noise_bump(nt, bsdf, scale=120.0, strength=0.1, coord='Object',
                   loc=(-400, -300))
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    M['leaf'] = m

    return M
