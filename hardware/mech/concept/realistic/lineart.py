# Line-art pad drawing of the rear board's top face, from the same illustrative placement as the renders.
import json, math
from PIL import Image, ImageDraw
rec = json.load(open("/tmp/rt/rear_top.json")); K = 14; W, H = 128, 68; M = 60
im = Image.new("RGB", (W * K + 2 * M, H * K + 2 * M), (250, 250, 247)); d = ImageDraw.Draw(im)
P = lambda x, y: (M + (x + W / 2) * K, M + (H / 2 - y) * K)
ink = (25, 25, 25); grey = (150, 150, 150)
out = [(-64, -34), (64, -34), (64, -7), (53.3, -7), (53.3, 7), (64, 7), (64, 34), (-64, 34), (-64, 7), (-53.3, 7), (-53.3, -7), (-64, -7)]
d.line([P(*p) for p in out] + [P(*out[0])], fill=ink, width=5, joint="curve")
BODY = dict(relay=(29, 12.7), ld03=(25.4, 25.4), fuse=(15.4, 5.35), ecap_tht=(8, 8), ind_radial=(8, 8), ecap_smd=(6.6, 6.6), soic16w=(10.3, 7.5), ssop20=(7.2, 5.3),
            soic8=(4.9, 3.9), fpc=(18, 4), mov=(4.2, 11), axial=(10, 4.6), tco=(9, 3.2))
for r in rec:
    a = math.radians(r["rot"]); ca, sa = math.cos(a), math.sin(a)
    tf = lambda dx, dy: P(r["x"] + dx * ca - dy * sa, r["y"] + dx * sa + dy * ca)
    if r["kind"] in BODY:
        bw, bh = BODY[r["kind"]]; c = [tf(-bw / 2, -bh / 2), tf(bw / 2, -bh / 2), tf(bw / 2, bh / 2), tf(-bw / 2, bh / 2)]
        if r["kind"] in ("ecap_tht", "ind_radial"): x, y = tf(0, 0); d.ellipse([x - 4 * K, y - 4 * K, x + 4 * K, y + 4 * K], outline=grey, width=2)
        else: d.line(c + [c[0]], fill=grey, width=2)
    for dx, dy, w, h, hole in r["pads"]:
        x, y = tf(dx, dy)
        if hole:
            R = w / 2 * K; d.ellipse([x - R, y - R, x + R, y + R], outline=ink, width=max(3, int((w - hole) / 2 * K)))
        else:
            c = [tf(dx - w / 2, dy - h / 2), tf(dx + w / 2, dy - h / 2), tf(dx + w / 2, dy + h / 2), tf(dx - w / 2, dy + h / 2)]
            d.polygon(c, fill=grey if w * h > 8 else ink)
for cx in (-34, 34):
    c = [P(cx - 17, -14), P(cx + 17, -14), P(cx + 17, 22), P(cx - 17, 22)]; d.line(c + [c[0]], fill=grey, width=2)
for y in range(-33, 34, 3): d.line([P(13.4, y), P(13.4, y + 1.6)], fill=grey, width=2)
for sx in (-60.3, 60.3):
    x, y = P(sx, 0); d.ellipse([x - 3.2 * K, y - 3.2 * K, x + 3.2 * K, y + 3.2 * K], outline=grey, width=2)
d.text((M, H * K + M + 18), "SWS rear board, top face. Illustrative placement, not the layout.  parts %03d" % len(rec), fill=(90, 90, 90))
im.save("/tmp/rt/lineart.png"); print("ok", im.size)
