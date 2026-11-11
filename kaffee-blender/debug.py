import bpy, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "coffee2.blend"))
p = bpy.context.preferences.addons["cycles"].preferences
p.compute_device_type = "OPTIX"; p.get_devices()
for d in p.devices: d.use = "NVIDIA" in d.name
sc = bpy.context.scene; sc.cycles.device = "GPU"; sc.cycles.samples = 32
sc.render.resolution_x, sc.render.resolution_y = 640, 360
mode = sys.argv[sys.argv.index("--") + 1]
if mode == "noglass":
    bpy.data.objects["Glas"].hide_render = True
if mode == "nocream":
    m = bpy.data.materials["Kaffee"].node_tree
    for n in m.nodes:
        if n.type == "VOLUME_PRINCIPLED":
            n.inputs["Density"].default_value = 0.0
if mode == "nocream_noglass":
    bpy.data.objects["Glas"].hide_render = True
    m = bpy.data.materials["Kaffee"].node_tree
    for n in m.nodes:
        if n.type == "VOLUME_PRINCIPLED": n.inputs["Density"].default_value = 0.0
for ob in bpy.data.objects: print(ob.name, ob.type, tuple(round(v, 3) for v in ob.location), tuple(round(v, 3) for v in ob.dimensions))
sc.frame_set(110)
sc.render.filepath = os.path.join(HERE, "dbg_" + mode + ".png")
bpy.ops.render.render(write_still=True)
