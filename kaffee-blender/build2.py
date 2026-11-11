"""Kaffee + Sahne cinematisch, GITTERLOS: prozedurales Volumen (Spieleindustrie-Trick).
blender -b -P build2.py -- build | render
Env: FRAMES, SAMPLES, RX, RY, FRAMELIST, OUT, F0, F1, EXPO
"""
import bpy, bmesh, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(HERE, "coffee2.blend")
stage = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "build"
E = lambda k, d: os.environ.get(k, d)
FRAMES = int(E("FRAMES", "240")); FPS = 24
FLOOR, SURF = 0.08, 1.15
AX, AY = 0.12, 0.0          # Auftreffpunkt der Sahne

def spin(name, profile, steps=128):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    vs = [bm.verts.new((r, 0, z)) for r, z in profile]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=steps, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons: p.use_smooth = True
    return ob

def new_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; return m
def prin(mat, **kw):
    n = mat.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        if k in n.inputs: n.inputs[k].default_value = v
    return n

# ------------------------------------------------------------------ Knoten-DSL
class G:
    def __init__(s, nt): s.nt = nt; s.N = nt.nodes; s.L = nt.links
    def put(s, inp, v):
        if isinstance(v, (int, float)): inp.default_value = v
        elif isinstance(v, (tuple, list)): inp.default_value = v
        else: s.L.new(v, inp)
    def m(s, op, a, b=None, clamp=False):
        n = s.N.new("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
        s.put(n.inputs[0], a)
        if b is not None: s.put(n.inputs[1], b)
        return n.outputs[0]
    def add(s, a, b, c=False): return s.m('ADD', a, b, c)
    def sub(s, a, b, c=False): return s.m('SUBTRACT', a, b, c)
    def mul(s, a, b, c=False): return s.m('MULTIPLY', a, b, c)
    def pw(s, a, b): return s.m('POWER', a, b)
    def mx(s, a, b): return s.m('MAXIMUM', a, b)
    def mn(s, a, b): return s.m('MINIMUM', a, b)
    def sq(s, a): return s.m('MULTIPLY', a, a)
    def ex(s, a): return s.m('POWER', 2.718281828, a)          # e^a
    def rng(s, v, a, b, c=0.0, d=1.0, smooth=True, clamp=True):
        n = s.N.new("ShaderNodeMapRange"); n.interpolation_type = 'SMOOTHSTEP' if smooth else 'LINEAR'; n.clamp = clamp
        for k, x in zip(("Value", "From Min", "From Max", "To Min", "To Max"), (v, a, b, c, d)): s.put(n.inputs[k], x)
        return n.outputs[0]
    def vm(s, op, a, b=None, scale=None):
        n = s.N.new("ShaderNodeVectorMath"); n.operation = op
        s.put(n.inputs[0], a)
        if b is not None: s.put(n.inputs[1], b)
        if scale is not None: s.put(n.inputs[3], scale)
        return n.outputs[0]
    def comb(s, x, y, z):
        n = s.N.new("ShaderNodeCombineXYZ"); s.put(n.inputs[0], x); s.put(n.inputs[1], y); s.put(n.inputs[2], z); return n.outputs[0]
    def sep(s, v):
        n = s.N.new("ShaderNodeSeparateXYZ"); s.put(n.inputs[0], v); return n.outputs[0], n.outputs[1], n.outputs[2]
    def noise(s, vec, scale=1.0, detail=4.0, rough=.55, w=None, color=False):
        n = s.N.new("ShaderNodeTexNoise"); n.noise_dimensions = '4D' if w is not None else '3D'
        try: n.noise_type = 'FBM'
        except Exception: pass
        s.put(n.inputs["Vector"], vec); s.put(n.inputs["Scale"], scale); s.put(n.inputs["Detail"], detail); s.put(n.inputs["Roughness"], rough)
        if w is not None: s.put(n.inputs["W"], w)
        return n.outputs["Color"] if color else n.outputs["Fac"]

def time_node(g):
    n = g.N.new("ShaderNodeValue"); fc = n.outputs[0].driver_add("default_value")
    fc.driver.type = 'SCRIPTED'; fc.driver.expression = f"frame/{FPS}"; return n.outputs[0]

def build_cream(mat):
    nt = mat.node_tree; g = G(nt)
    tc = g.N.new("ShaderNodeTexCoord"); P = tc.outputs["Object"]
    t = time_node(g)
    # Strömungs-Advektion: Muster wandert nach unten (Domain-Warp, wie in Spiele-VFX)
    adv = g.comb(0, 0, g.mul(t, 1.5))
    x, y, z = g.sep(P)
    d0 = g.sub(SURF, z)                                    # Tiefe unter Oberfläche
    dcl = g.rng(d0, 0.0, 1.1, 0.0, 1.0, smooth=False)
    # Warp-Vektor: wächst mit der Tiefe -> Turbulenz nimmt zu
    wn = g.noise(g.vm('ADD', g.vm('SCALE', P, scale=3.0), adv), 1.0, 4.0, .55, color=True)
    wv = g.vm('SCALE', g.vm('SUBTRACT', wn, (.5, .5, .5)), scale=g.mul(g.add(.04, g.mul(dcl, .24)), 2.0))
    Pw = g.vm('ADD', P, wv)
    xw, yw, zw = g.sep(Pw)
    dw = g.sub(SURF, zw)
    rw = g.m('SQRT', g.add(g.sq(g.sub(xw, AX)), g.sq(g.sub(yw, AY))))
    # Detailrauschen (feine Fäden, wandert nach unten)
    nd = g.noise(g.vm('ADD', g.vm('SCALE', Pw, scale=9.0), g.comb(0, 0, g.mul(t, 2.2))), 1.0, 5.0, .62)
    # --- Strahl + Kopf (Pilzkappe)
    tt = g.mx(g.sub(t, 0.35), 0.0)
    H = g.mul(g.sub(1.0, g.ex(g.mul(tt, -1.55))), 1.18)    # Kopftiefe
    dclw = g.rng(dw, 0.0, 1.1, 0.0, 1.0, smooth=False)
    rs = g.add(.05, g.mul(dclw, .17))
    stem = g.pw(g.m('SUBTRACT', 1.0, g.m('DIVIDE', rw, rs), True), 1.4)
    front = g.rng(dw, H, g.sub(H, .16), 0.0, 1.0)
    top = g.rng(dw, -.01, .03, 0.0, 1.0)
    stemE = g.mul(g.mul(stem, front), top)
    Hc = g.mn(H, 1.0)
    Rc = g.add(.075, g.mul(Hc, .17))
    dcap = g.sub(dw, g.sub(H, .11))
    capv = g.m('SUBTRACT', 1.0, g.add(g.sq(g.m('DIVIDE', rw, Rc)), g.sq(g.m('DIVIDE', dcap, g.mul(Rc, .55)))), True)
    capE = g.mul(capv, g.rng(H, .04, .12, 0.0, 1.0))
    Eenv = g.mx(stemE, capE)
    Dp = g.m('SUBTRACT', g.mul(Eenv, 1.35), g.mul(g.sub(1.0, nd), .6), True)
    # --- Ausbreitung am Boden (Schwerkraftströmung)
    tf = g.mx(g.sub(t, 1.75), 0.0)
    Rf = g.add(.12, g.mul(g.sub(1.0, g.ex(g.mul(tf, -1.3))), .85))
    lay = g.rng(rw, Rf, g.mul(Rf, .5), 0.0, 1.0)
    hf = g.add(.04, g.mul(tf, .05))
    vert = g.ex(g.m('DIVIDE', g.mul(g.mx(g.sub(zw, FLOOR), 0.0), -1.0), hf))
    fl = g.mul(g.mul(lay, vert), g.rng(tf, 0.0, .2, 0.0, 1.0))
    Dfl = g.m('SUBTRACT', g.mul(fl, 1.25), g.mul(g.sub(1.0, nd), .5), True)
    # --- Trübung: Sahne vermischt sich langsam zu Milchkaffee
    nl = g.noise(g.vm('ADD', g.vm('SCALE', Pw, scale=2.2), g.vm('SCALE', adv, scale=.12)), 1.0, 3.0, .5)
    vw = g.add(.35, g.mul(g.ex(g.mul(g.mx(g.sub(zw, FLOOR), 0.0), -.9)), .65))
    Hz = g.mul(g.mul(g.rng(t, 2.2, 8.0, 0.0, .55), vw), g.rng(nl, .35, .65, .12, 1.0))
    # --- rollende Wolke: quillt nach dem Eingießen vom Boden hoch und verwirbelt
    hb = g.add(.20, g.mul(g.sub(1.0, g.ex(g.mul(tf, -.55))), .62))
    zr = g.mx(g.sub(zw, FLOOR), 0.0)
    bvert = g.rng(zr, hb, g.mul(hb, .35), 0.0, 1.0)
    nb = g.noise(g.vm('ADD', g.vm('SCALE', Pw, scale=3.6), g.vm('SCALE', adv, scale=.3)), 1.0, 5.0, .62)
    bil = g.mul(g.mul(g.rng(nb, .40, .62, 0.0, 1.0), bvert), g.rng(tf, 0.0, .5, 0.0, 1.0))
    bil = g.mul(bil, g.sub(1.0, g.rng(t, 6.5, 10.0, 0.0, .55)))
    Dbl = g.mul(bil, .95)
    D = g.mx(g.mx(Dp, Dbl), g.mx(Dfl, Hz))
    fh = g.m('DIVIDE', Hz, g.add(D, .002), True)
    mix = g.N.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    g.put(mix.inputs[0], g.mul(fh, .85)); mix.inputs[6].default_value = (.97, .90, .76, 1); mix.inputs[7].default_value = (.78, .55, .36, 1)
    pv = g.N.new("ShaderNodeVolumePrincipled")
    pv.inputs["Anisotropy"].default_value = .3
    g.L.new(mix.outputs[2], pv.inputs["Color"]); g.put(pv.inputs["Density"], g.mul(D, 48.0))
    if "Emission Strength" in pv.inputs:
        g.put(pv.inputs["Emission Strength"], g.mul(D, 2.6)); pv.inputs["Emission Color"].default_value = (1, .90, .72, 1)
    # Kaffee-Grundabsorption
    va = g.N.new("ShaderNodeVolumeAbsorption"); va.inputs["Color"].default_value = (.50, .29, .16, 1); va.inputs["Density"].default_value = 2.1
    ad = g.N.new("ShaderNodeAddShader"); g.L.new(va.outputs[0], ad.inputs[0]); g.L.new(pv.outputs[0], ad.inputs[1])
    g.L.new(ad.outputs[0], nt.nodes["Material Output"].inputs["Volume"])

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.frame_start, sc.frame_end = 1, FRAMES; sc.render.fps = FPS
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0)); tb = bpy.context.object; tb.name = "Tisch"
    m = new_mat("Tisch"); prin(m, **{"Base Color": (.006, .005, .004, 1), "Roughness": .38, "Specular IOR Level": .35}); tb.data.materials.append(m)
    glass = spin("Glas", [(0, 0), (.83, 0), (.85, .02), (.85, 1.28), (.845, 1.30), (.825, 1.30), (.82, 1.28), (.82, FLOOR), (0, FLOOR)], 256)
    # dünnes Glas ohne Brechung (Standard in Produktfilmen): Fresnel-Spiegelung + durchsichtig
    gm = new_mat("Glas"); ntg = gm.node_tree; ntg.nodes.remove(ntg.nodes["Principled BSDF"])
    fr = ntg.nodes.new("ShaderNodeLayerWeight"); fr.inputs["Blend"].default_value = .45     # seitenunabhängig (kein Totalreflex von innen)
    fs = ntg.nodes.new("ShaderNodeMath"); fs.operation = 'MULTIPLY'; fs.inputs[1].default_value = .5; ntg.links.new(fr.outputs["Facing"], fs.inputs[0])
    gg = ntg.nodes.new("ShaderNodeBsdfGlossy"); gg.inputs["Roughness"].default_value = .01
    gt = ntg.nodes.new("ShaderNodeBsdfTransparent"); gx = ntg.nodes.new("ShaderNodeMixShader")
    ntg.links.new(fs.outputs[0], gx.inputs[0]); ntg.links.new(gt.outputs[0], gx.inputs[1]); ntg.links.new(gg.outputs[0], gx.inputs[2])
    ntg.links.new(gx.outputs[0], ntg.nodes["Material Output"].inputs["Surface"]); glass.data.materials.append(gm)
    # sichtbarer Studiohintergrund mit weichem Verlauf (Emission), beleuchtet zugleich die Szene
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 15.0, 4.0), rotation=(math.radians(90), 0, 0)); bgp = bpy.context.object; bgp.name = "Hintergrund"; bgp.scale = (60, 34, 1)
    bgm = new_mat("Hintergrund"); ntb = bgm.node_tree; ntb.nodes.remove(ntb.nodes["Principled BSDF"])
    tcb = ntb.nodes.new("ShaderNodeTexCoord"); gr = ntb.nodes.new("ShaderNodeTexGradient"); gr.gradient_type = 'SPHERICAL'
    mp = ntb.nodes.new("ShaderNodeMapping"); mp.inputs["Location"].default_value = (-.5, -.5, 0)
    ntb.links.new(tcb.outputs["Generated"], mp.inputs["Vector"]); ntb.links.new(mp.outputs[0], gr.inputs["Vector"])
    cr = ntb.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.interpolation = 'EASE'
    cr.color_ramp.elements[0].position = 0.12; cr.color_ramp.elements[0].color = (.003, .002, .002, 1)
    cr.color_ramp.elements[1].position = .80; cr.color_ramp.elements[1].color = (1.0, .74, .46, 1)
    ntb.links.new(gr.outputs["Fac"], cr.inputs["Fac"])
    em = ntb.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.7
    ntb.links.new(cr.outputs["Color"], em.inputs["Color"]); ntb.links.new(em.outputs[0], ntb.nodes["Material Output"].inputs["Surface"]); bgp.data.materials.append(bgm)
    cof = spin("Kaffee", [(0, FLOOR + .008), (.797, FLOOR + .008), (.797, SURF), (0, SURF)], 192)
    cm = new_mat("Kaffee")
    ntc = cm.node_tree; ntc.nodes.remove(ntc.nodes["Principled BSDF"])
    tr = ntc.nodes.new("ShaderNodeBsdfTransparent"); ntc.links.new(tr.outputs[0], ntc.nodes["Material Output"].inputs["Surface"])
    build_cream(cm); cof.data.materials.append(cm)
    # Kaffeespiegel: eigene Fläche mit Fresnel-Spiegelung (Rest durchsichtig)
    bpy.ops.mesh.primitive_circle_add(vertices=128, radius=.797, fill_type='NGON', location=(0, 0, SURF + .0008)); sp = bpy.context.object; sp.name = "Spiegel"
    spm = new_mat("Spiegel"); nts = spm.node_tree; nts.nodes.remove(nts.nodes["Principled BSDF"])
    lw = nts.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = .25
    gl = nts.nodes.new("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = .015; gl.inputs["Color"].default_value = (.9, .85, .8, 1)
    tr2 = nts.nodes.new("ShaderNodeBsdfTransparent"); mx = nts.nodes.new("ShaderNodeMixShader")
    nts.links.new(lw.outputs["Fresnel"], mx.inputs[0]); nts.links.new(tr2.outputs[0], mx.inputs[1]); nts.links.new(gl.outputs[0], mx.inputs[2])
    nts.links.new(mx.outputs[0], nts.nodes["Material Output"].inputs["Surface"]); sp.data.materials.append(spm)
    # Sahnestrahl: Ursprung oben, wächst nach unten, danach reißt er ab
    pe = int(FPS * 3.0); top = 2.9
    st = spin("Strahl", [(0, 0), (.036, 0), (.031, -(top - SURF) * .5), (.037, -(top - SURF)), (0, -(top - SURF))], 24)
    st.location = (AX, AY, top)
    sm = new_mat("Strahl"); prin(sm, **{"Base Color": (1.0, .95, .84, 1), "Roughness": .1, "Coat Weight": .7, "Emission Color": (1, .93, .8, 1), "Emission Strength": .9}); st.data.materials.append(sm)
    for f, s in ((1, .001), (9, 1.0), (pe - 4, 1.0), (pe + 8, .001)):
        st.scale = (1 if f < pe else .2, 1 if f < pe else .2, s); st.keyframe_insert("scale", frame=f)
    # Kamera: ruhige Fahrt + Tiefenschärfe
    emp = bpy.data.objects.new("Ziel", None); sc.collection.objects.link(emp); emp.location = (0, 0, .72)
    cam = bpy.data.cameras.new("Kamera"); cam.lens = 55; cam.sensor_width = 36
    cam.dof.use_dof = True; cam.dof.focus_object = emp; cam.dof.aperture_fstop = 2.0
    co = bpy.data.objects.new("Kamera", cam); sc.collection.objects.link(co); sc.camera = co
    co.parent = emp; co.location = (0, -6.2, .75)
    tc = co.constraints.new("TRACK_TO"); tc.target = emp; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
    emp.rotation_euler = (0, 0, math.radians(-24)); emp.keyframe_insert("rotation_euler", frame=1)
    emp.rotation_euler = (0, 0, math.radians(16)); emp.keyframe_insert("rotation_euler", frame=FRAMES)
    co.location = (0, -6.4, 1.0); co.keyframe_insert("location", frame=1)
    co.location = (0, -4.9, .85); co.keyframe_insert("location", frame=FRAMES)
    def area(name, loc, sx, sy, energy, color):
        l = bpy.data.lights.new(name, 'AREA'); l.shape = 'RECTANGLE'; l.size = sx; l.size_y = sy; l.energy = energy; l.color = color
        o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
        c = o.constraints.new("TRACK_TO"); c.target = emp; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    def spot(name, loc, energy, color, deg=24, soft=.7):
        l = bpy.data.lights.new(name, 'SPOT'); l.energy = energy; l.color = color; l.spot_size = math.radians(deg); l.spot_blend = .7; l.shadow_soft_size = soft
        o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
        c = o.constraints.new("TRACK_TO"); c.target = emp; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    spot("Key links", (-3.4, -2.4, 2.4), 1100, (1.0, .95, .9), 22, .8)
    spot("Kante rechts", (3.6, 1.0, 1.3), 1600, (.72, .84, 1.0), 20, .5)
    spot("Oben", (0, -.3, 3.6), 350, (1, 1, 1), 24, .8)
    w = bpy.data.worlds.new("Welt"); w.use_nodes = True; sc.world = w
    bg = w.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (.020, .014, .011, 1); bg.inputs["Strength"].default_value = 1.0
    r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y = 1920, 1080
    cy = sc.cycles; cy.samples = 96; cy.use_adaptive_sampling = True; cy.adaptive_threshold = .02
    cy.max_bounces = 12; cy.transmission_bounces = 14; cy.volume_bounces = 6; cy.glossy_bounces = 6
    cy.volume_step_rate = 1.0; cy.volume_max_steps = 1024; cy.use_denoising = True
    cy.caustics_reflective = False; cy.caustics_refractive = False; cy.sample_clamp_indirect = 6.0; cy.sample_clamp_direct = 20.0
    try: cy.denoiser = 'OPTIX'
    except Exception: pass
    try: sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception: pass
    sc.view_settings.exposure = float(E("EXPO", "0.0"))
    bpy.ops.wm.save_as_mainfile(filepath=BLEND); print("BUILD OK")

def gpu():
    p = bpy.context.preferences.addons["cycles"].preferences
    for t in ("OPTIX", "CUDA"):
        try:
            p.compute_device_type = t; p.get_devices(); ok = False
            for dv in p.devices:
                dv.use = ("NVIDIA" in dv.name); ok = ok or dv.use
            if ok: bpy.context.scene.cycles.device = 'GPU'; print("GPU", t, [d.name for d in p.devices if d.use]); return
        except Exception as ex: print("gpu fail", t, ex)

def render():
    bpy.ops.wm.open_mainfile(filepath=BLEND); gpu()
    sc = bpy.context.scene; r = sc.render
    r.resolution_x, r.resolution_y = int(E("RX", "1920")), int(E("RY", "1080"))
    sc.cycles.samples = int(E("SAMPLES", "96"))
    out = E("OUT", os.path.join(HERE, "frames2")); os.makedirs(out, exist_ok=True)
    r.image_settings.file_format = 'PNG'; r.image_settings.color_depth = '8'
    fl = E("FRAMELIST", "")
    if fl:
        for f in [int(x) for x in fl.split(",")]:
            sc.frame_set(f); r.filepath = os.path.join(out, f"still_{f:04d}.png"); bpy.ops.render.render(write_still=True)
    else:
        r.filepath = os.path.join(out, "f_"); sc.frame_start = int(E("F0", "1")); sc.frame_end = int(E("F1", str(FRAMES)))
        bpy.ops.render.render(animation=True)
    print("RENDER OK")

{"build": build, "render": render}[stage]()
