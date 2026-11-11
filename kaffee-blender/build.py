"""Kaffee + Sahne, cinematisch. Aufruf:
blender -b -P build.py -- <stage>      stage = build | bake | render
Umgebungsvariablen: RES (Gitter, 64 Test / 128 final), FRAMES, NOISE (0/1), SAMPLES, RX, RY, FRAMELIST (z.B. 30,60,100), OUT
"""
import bpy, bmesh, math, os, sys, mathutils
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(HERE, "coffee.blend")
CACHE = os.path.join(HERE, "cache")
stage = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "build"
E = lambda k, d: os.environ.get(k, d)
FRAMES = int(E("FRAMES", "168"))

def spin(name, profile, steps=96):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new((r, 0, z)) for r, z in profile]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=steps, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons: p.use_smooth = True
    return ob

def principled(mat, **kw):
    n = mat.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        if k in n.inputs: n.inputs[k].default_value = v
    return n

def new_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; return m

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, FRAMES
    sc.render.fps = 24
    FLOOR, SURF = 0.15, 1.15      # Boden innen / Kaffeespiegel (z)

    # ---- Tisch ----
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0)); table = bpy.context.object; table.name = "Tisch"
    m = new_mat("Tisch"); principled(m, **{"Base Color": (.018, .014, .012, 1), "Roughness": .22, "Specular IOR Level": .6})
    table.data.materials.append(m)

    # ---- Glas ----
    glass = spin("Glas", [(0, 0), (.82, 0), (.85, .03), (.85, 1.28), (.84, 1.30), (.81, 1.30), (.80, 1.28), (.80, FLOOR), (0, FLOOR)], 128)
    gm = new_mat("Glas"); principled(gm, **{"Base Color": (1, 1, 1, 1), "Roughness": 0.0, "IOR": 1.5, "Transmission Weight": 1.0})
    glass.data.materials.append(gm)

    # ---- Kaffee (Volumen-Absorption + Wasseroberfläche) ----
    cof = spin("Kaffee", [(0, FLOOR + .002), (.797, FLOOR + .002), (.797, SURF), (0, SURF)], 128)
    cm = new_mat("Kaffee"); nt = cm.node_tree
    principled(cm, **{"Base Color": (1, 1, 1, 1), "Roughness": 0.0, "IOR": 1.33, "Transmission Weight": 1.0})
    va = nt.nodes.new("ShaderNodeVolumeAbsorption"); va.inputs["Color"].default_value = (.20, .075, .03, 1); va.inputs["Density"].default_value = 11.0
    vs = nt.nodes.new("ShaderNodeVolumeScatter"); vs.inputs["Color"].default_value = (.12, .05, .02, 1); vs.inputs["Density"].default_value = 1.2
    add = nt.nodes.new("ShaderNodeAddShader"); nt.links.new(va.outputs[0], add.inputs[0]); nt.links.new(vs.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], nt.nodes["Material Output"].inputs["Volume"])
    cof.data.materials.append(cm)

    # ---- Ring-Hindernis: Ecken der Box sperren, Strömung bleibt im runden Glas ----
    ring = spin("Ring", [(.80, FLOOR - .2), (1.4, FLOOR - .2), (1.4, SURF + .3), (.80, SURF + .3)], 128)
    ring.display_type = 'WIRE'; ring.hide_render = True

    # ---- Domain ----
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, (FLOOR + SURF) / 2)); dom = bpy.context.object; dom.name = "Domain"
    dom.scale = (1.6, 1.6, SURF - FLOOR)
    bpy.context.view_layer.objects.active = dom
    bpy.ops.object.modifier_add(type='FLUID'); fm = dom.modifiers["Fluid"]; fm.fluid_type = 'DOMAIN'
    d = fm.domain_settings
    d.domain_type = 'GAS'; d.resolution_max = int(E("RES", "64"))
    d.cache_type = 'ALL'; d.cache_directory = CACHE
    d.cache_frame_start, d.cache_frame_end = 1, FRAMES
    d.alpha = float(E("ALPHA", "2.5"))       # Dichte-Auftrieb: positiv = sinkt
    d.beta = 0.0                              # keine Wärme
    d.vorticity = float(E("VORT", "0.5"))
    d.use_dissolve_smoke = False
    d.use_noise = E("NOISE", "0") == "1"
    if d.use_noise: d.noise_scale = 2
    d.use_adaptive_timesteps = True
    for a in ("use_collision_border_front", "use_collision_border_back", "use_collision_border_left", "use_collision_border_right", "use_collision_border_top", "use_collision_border_bottom"):
        if hasattr(d, a): setattr(d, a, True)
    dm = new_mat("Sahne"); nt = dm.node_tree
    for n in list(nt.nodes):
        if n.type == 'BSDF_PRINCIPLED': nt.nodes.remove(n)
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (.96, .88, .72, 1); pv.inputs["Density"].default_value = 40.0
    pv.inputs["Anisotropy"].default_value = .25
    if "Emission Strength" in pv.inputs:
        pv.inputs["Emission Strength"].default_value = .04; pv.inputs["Emission Color"].default_value = (1, .85, .6, 1)
    nt.links.new(pv.outputs[0], nt.nodes["Material Output"].inputs["Volume"])
    dom.data.materials.append(dm)
    dom.display_type = 'WIRE'

    # ---- Hindernis-Ring als Effektor ----
    bpy.context.view_layer.objects.active = ring
    bpy.ops.object.modifier_add(type='FLUID'); em = ring.modifiers["Fluid"]; em.fluid_type = 'EFFECTOR'
    em.effector_settings.effector_type = 'COLLISION'

    # ---- Einlauf ----
    bpy.ops.mesh.primitive_cylinder_add(radius=.05, depth=.1, location=(.12, 0, SURF - .07)); flow = bpy.context.object; flow.name = "Einlauf"
    bpy.context.view_layer.objects.active = flow
    bpy.ops.object.modifier_add(type='FLUID'); ff = flow.modifiers["Fluid"]; ff.fluid_type = 'FLOW'
    fs = ff.flow_settings
    fs.flow_type = 'SMOKE'; fs.flow_behavior = 'INFLOW'; fs.flow_source = 'MESH'
    fs.temperature = 0.0; fs.density = 1.0
    fs.use_initial_velocity = True; fs.velocity_coord = (0, 0, -float(E("JET", "1.6")))
    flow.hide_render = True
    pour_end = int(E("POUREND", "64"))
    fs.use_inflow = True; fs.keyframe_insert("use_inflow", frame=1)
    fs.use_inflow = False; fs.keyframe_insert("use_inflow", frame=pour_end)

    # ---- sichtbarer Sahne-Strahl (Ursprung oben, wächst nach unten) ----
    top = 2.7
    st = spin("Strahl", [(0, 0), (.035, 0), (.030, -(top - SURF) * .5), (.036, -(top - SURF)), (0, -(top - SURF))], 24)
    st.location = (.12, 0, top)
    sm = new_mat("Strahl"); principled(sm, **{"Base Color": (.95, .87, .70, 1), "Roughness": .12, "Subsurface Weight": .5, "Coat Weight": .6})
    st.data.materials.append(sm)
    st.scale = (1, 1, .001); st.keyframe_insert("scale", frame=1)
    st.scale = (1, 1, 1);    st.keyframe_insert("scale", frame=9)
    st.keyframe_insert("scale", frame=pour_end - 4)
    st.scale = (.25, .25, .001); st.keyframe_insert("scale", frame=pour_end + 8)

    # ---- Kamera mit Fahrt ----
    emp = bpy.data.objects.new("Ziel", None); sc.collection.objects.link(emp); emp.location = (0, 0, .78)
    cam = bpy.data.cameras.new("Kamera"); cam.lens = 85; cam.dof.use_dof = True; cam.dof.focus_object = emp; cam.dof.aperture_fstop = 2.8
    co = bpy.data.objects.new("Kamera", cam); sc.collection.objects.link(co); sc.camera = co
    co.parent = emp; co.location = (0, -4.4, .35)
    tc = co.constraints.new("TRACK_TO"); tc.target = emp; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
    emp.rotation_euler = (0, 0, math.radians(-22)); emp.keyframe_insert("rotation_euler", frame=1)
    emp.rotation_euler = (0, 0, math.radians(14));  emp.keyframe_insert("rotation_euler", frame=FRAMES)
    co.location = (0, -4.9, .55); co.keyframe_insert("location", frame=1)
    co.location = (0, -3.6, .25); co.keyframe_insert("location", frame=FRAMES)
    for ob in (emp, co):
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves if hasattr(ob.animation_data.action, "fcurves") else []:
                for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'

    # ---- Licht ----
    def area(name, loc, size, energy, color, target=(0, 0, .75), shape='RECTANGLE', sy=None):
        l = bpy.data.lights.new(name, 'AREA'); l.energy = energy; l.size = size; l.color = color
        if sy: l.shape = 'RECTANGLE'; l.size_y = sy
        o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
        c = o.constraints.new("TRACK_TO"); c.target = emp; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
        return o
    area("Rim hinten", (0, 3.2, 1.6), 1.8, 1800, (1.0, .93, .82), sy=2.4)
    area("Key links", (-2.6, -1.8, 2.6), 1.6, 700, (1.0, .95, .9), sy=1.0)
    area("Kante rechts", (2.8, 1.2, 1.2), .5, 900, (.75, .85, 1.0), sy=2.6)
    w = bpy.data.worlds.new("Welt"); w.use_nodes = True; sc.world = w
    bg = w.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (.006, .007, .010, 1); bg.inputs["Strength"].default_value = 1.0

    # ---- Render ----
    r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y = 1920, 1080; r.resolution_percentage = 100
    cy = sc.cycles; cy.samples = 96; cy.use_adaptive_sampling = True; cy.adaptive_threshold = .02
    cy.max_bounces = 12; cy.transmission_bounces = 14; cy.volume_bounces = 5; cy.glossy_bounces = 6
    cy.volume_step_rate = 1.0; cy.volume_max_steps = 1024
    cy.use_denoising = True
    try: cy.denoiser = 'OPTIX'
    except Exception: pass
    try: sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception: pass
    sc.view_settings.exposure = float(E("EXPO", "0.0"))
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("BUILD OK", BLEND)

def gpu():
    p = bpy.context.preferences.addons["cycles"].preferences
    for t in ("OPTIX", "CUDA"):
        try:
            p.compute_device_type = t; p.get_devices(); ok = False
            for dv in p.devices:
                dv.use = dv.type != 'CPU'; ok = ok or dv.use
            if ok: bpy.context.scene.cycles.device = 'GPU'; print("GPU", t, [d.name for d in p.devices if d.use]); return
        except Exception as ex: print("gpu fail", t, ex)

def bake():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    dom = bpy.data.objects["Domain"]; bpy.context.view_layer.objects.active = dom
    for o in bpy.data.objects: o.select_set(o is dom)
    bpy.ops.fluid.bake_data()
    if dom.modifiers["Fluid"].domain_settings.use_noise: bpy.ops.fluid.bake_noise()
    bpy.ops.wm.save_mainfile()
    print("BAKE OK")

def render():
    bpy.ops.wm.open_mainfile(filepath=BLEND); gpu()
    sc = bpy.context.scene; r = sc.render
    r.resolution_x, r.resolution_y = int(E("RX", "1920")), int(E("RY", "1080"))
    sc.cycles.samples = int(E("SAMPLES", "96"))
    out = E("OUT", os.path.join(HERE, "frames"))
    os.makedirs(out, exist_ok=True)
    r.image_settings.file_format = 'PNG'; r.image_settings.color_depth = '8'
    fl = E("FRAMELIST", "")
    if fl:
        for f in [int(x) for x in fl.split(",")]:
            sc.frame_set(f); r.filepath = os.path.join(out, f"still_{f:04d}.png"); bpy.ops.render.render(write_still=True)
    else:
        r.filepath = os.path.join(out, "f_"); sc.frame_start = int(E("F0", "1")); sc.frame_end = int(E("F1", str(FRAMES)))
        bpy.ops.render.render(animation=True)
    print("RENDER OK")

{"build": build, "bake": bake, "render": render}[stage]()
