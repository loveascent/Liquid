import bpy, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "coffee2.blend"))
for name in ("Glas", "Kaffee"):
    me = bpy.data.objects[name].data
    out = inn = 0; ex = []
    for p in me.polygons:
        c = p.center; rad = math.hypot(c.x, c.y)
        if rad < 0.7: continue          # nur Seitenwände
        d = (p.normal.x * c.x + p.normal.y * c.y) / (rad + 1e-9)
        if d > 0: out += 1
        else: inn += 1; ex.append((round(rad, 3), round(c.z, 2)))
    print(name, "faces", len(me.polygons), "radial-nach-aussen", out, "nach-innen", inn, ex[:6])
