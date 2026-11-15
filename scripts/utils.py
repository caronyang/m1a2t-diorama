"""Shared helpers for the miniature diorama build (Blender 4.5)."""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix, Euler

# ---------------------------------------------------------------- scene / io

def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.objects,
                  bpy.data.cameras, bpy.data.lights, bpy.data.images):
        for b in list(block):
            try:
                block.remove(b)
            except Exception:
                pass


def collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


# ---------------------------------------------------------------- colors

def srgb(hexstr):
    hexstr = hexstr.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(hexstr[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


# ---------------------------------------------------------------- materials

def base_material(name, color, rough=0.6, metal=0.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (500, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (150, 0)
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = spec
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    m.diffuse_color = color
    return m, nt, bsdf


def add_noise_bump(nt, bsdf, scale=30.0, detail=6.0, strength=0.25, coord='Object',
                   coord_obj=None, loc=(-500, -400)):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.location = loc
    tc.object = coord_obj
    if coord == 'Object':
        out = tc.outputs['Object']
    elif coord == 'Generated':
        out = tc.outputs['Generated']
    else:
        out = tc.outputs['Normal']
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.location = (loc[0] + 200, loc[1])
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = 0.6
    nt.links.new(out, n.inputs['Vector'])
    b = nt.nodes.new('ShaderNodeBump')
    b.location = (loc[0] + 400, loc[1])
    b.inputs['Strength'].default_value = strength
    b.inputs['Distance'].default_value = 0.004
    nt.links.new(n.outputs['Fac'], b.inputs['Height'])
    nt.links.new(b.outputs['Normal'], bsdf.inputs['Normal'])
    return n, b


# ---------------------------------------------------------------- geometry

def mesh_object(name, verts, faces, mat, coll, smooth=False, face_mats=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if face_mats:
        for p, mi in zip(me.polygons, face_mats):
            p.material_index = mi
            p.use_smooth = smooth
    else:
        for p in me.polygons:
            p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if isinstance(mat, (list, tuple)):
        for m in mat:
            me.materials.append(m)
    elif mat is not None:
        me.materials.append(mat)
    return ob


def obj_from_bm(bm, name, mat, coll, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.update()
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if isinstance(mat, (list, tuple)):
        for m in mat:
            me.materials.append(m)
    elif mat is not None:
        me.materials.append(mat)
    return ob


def bm_cube(bm, matrix, bevel=0.0):
    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=matrix)
    if bevel > 0:
        edges = [e for e in ret['verts'][0].link_edges] if ret.get('verts') else []
        # bevel the new geometry only: collect faces linked to new verts
        verts = ret['verts']
        edges = set()
        for v in verts:
            edges.update(v.link_edges)
        bmesh.ops.bevel(bm, geom=list(edges), offset=bevel, segments=2,
                        profile=0.7, affect='EDGES', clamp_overlap=True)
    return ret


def add_box(name, center, size, mat, coll, rot=(0, 0, 0), bevel=0.0, smooth=False):
    bm = bmesh.new()
    m = (Matrix.Translation(Vector(center)) @
         Euler(rot, 'XYZ').to_matrix().to_4x4() @
         Matrix.Diagonal(Vector((size[0], size[1], size[2], 1.0))))
    verts = bmesh.ops.create_cube(bm, size=1.0, matrix=m)['verts']
    if bevel > 0:
        edges = set()
        for v in verts:
            edges.update(v.link_edges)
        bmesh.ops.bevel(bm, geom=list(edges), offset=bevel, segments=2,
                        profile=0.7, affect='EDGES', clamp_overlap=True)
    return obj_from_bm(bm, name, mat, coll, smooth)


def add_cyl(name, center, radius, depth, mat, coll, axis='Z', segs=24,
            r2=None, rot=(0, 0, 0), smooth=True, bevel=0.0):
    bm = bmesh.new()
    r2 = radius if r2 is None else r2
    m = (Matrix.Translation(Vector(center)) @
         Euler(rot, 'XYZ').to_matrix().to_4x4())
    if axis == 'X':
        m = m @ Matrix.Rotation(math.radians(90), 4, 'Y')
    elif axis == 'Y':
        m = m @ Matrix.Rotation(math.radians(90), 4, 'X')
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                          radius1=radius, radius2=r2, depth=depth, matrix=m)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2,
                        affect='EDGES', clamp_overlap=True)
    return obj_from_bm(bm, name, mat, coll, smooth)


def add_ico(name, center, radius, mat, coll, subdiv=2, scale=(1, 1, 1),
            rot=(0, 0, 0), disp=0.0, seed=0, smooth=True, flat_bottom=None):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    m = (Matrix.Translation(Vector(center)) @
         Euler(rot, 'XYZ').to_matrix().to_4x4() @
         Matrix.Diagonal(Vector((scale[0], scale[1], scale[2], 1.0))))
    if disp > 0:
        rnd = random.Random(seed)
        for v in bm.verts:
            n = v.co.normalized()
            v.co += n * (rnd.uniform(-1, 1) * disp)
    bmesh.ops.transform(bm, matrix=m, verts=list(bm.verts))
    if flat_bottom is not None:
        for v in bm.verts:
            if v.co.z < flat_bottom:
                v.co.z = flat_bottom
    return obj_from_bm(bm, name, mat, coll, smooth)


def add_loft(name, rings, mat, coll, close_front=True, close_back=True,
             bevel=0.0, smooth=False):
    """rings: list of lists of (y,z) at increasing x. All rings same length."""
    verts = []
    for (x, ring) in rings:
        for (y, z) in ring:
            verts.append((x, y, z))
    n = len(rings[0][1])
    faces = []
    for i in range(len(rings) - 1):
        for j in range(n):
            a = i * n + j
            b = i * n + (j + 1) % n
            c = (i + 1) * n + (j + 1) % n
            d = (i + 1) * n + j
            faces.append((a, b, c, d))
    if close_front:
        faces.append(tuple(range(n))[::-1])
    if close_back:
        faces.append(tuple(range((len(rings) - 1) * n, len(rings) * n)))
    ob = mesh_object(name, verts, faces, mat, coll, smooth=smooth)
    if bevel > 0:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2,
                        profile=0.7, affect='EDGES', clamp_overlap=True)
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
    return ob


def rect_ring(hw, ztop, zbot, chamfer=0.0):
    if chamfer <= 0:
        return [(-hw, ztop), (hw, ztop), (hw, zbot), (-hw, zbot)]
    c = chamfer
    return [(-hw + c, ztop), (hw - c, ztop), (hw, ztop - c),
            (hw, zbot + c), (hw - c, zbot), (-hw + c, zbot),
            (-hw, zbot + c), (-hw, ztop - c)]


def merge_objects(objs, name, coll=None):
    """Join mesh objects into a single object using the join operator."""
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def tri_prism(name, p0, p1, p2, thickness, mat, coll, normal=(0, 1, 0)):
    """Extruded triangle used for pennants / markings."""
    n = Vector(normal).normalized() * (thickness * 0.5)
    a, b, c = Vector(p0), Vector(p1), Vector(p2)
    verts = [a - n, b - n, c - n, a + n, b + n, c + n]
    faces = [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]
    return mesh_object(name, [tuple(v) for v in verts], faces, mat, coll, smooth=False)
