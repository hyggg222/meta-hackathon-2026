import base64, colorsys, json, sys
import numpy as np
from PIL import Image, ImageDraw

img_path, masks_path, out_path = sys.argv[1:4]
img = Image.open(img_path).convert("RGB")
W, H = img.size
masks = json.load(open(masks_path))
scale = max(3, 1400 // max(W, H))
big = img.resize((W * scale, H * scale), Image.LANCZOS).convert("RGBA")
layer = np.zeros((H, W, 4), dtype=np.uint8)
info = []
for k, m in enumerate(masks):
    b = m["bounds"]
    w, h = b["right"] - b["left"], b["bottom"] - b["top"]
    ras = np.frombuffer(base64.b64decode(m["b64"]), dtype=np.uint8).reshape(h, w)
    r, g, bl = [int(c * 255) for c in colorsys.hsv_to_rgb(k / len(masks), 0.9, 1.0)]
    sub = layer[b["top"]:b["bottom"], b["left"]:b["right"]]
    sub[ras > 0] = (r, g, bl, 150)
    info.append((m["id"], b, int(ras.sum()), (r, g, bl)))
ov = Image.fromarray(layer).resize((W * scale, H * scale), Image.NEAREST)
big = Image.alpha_composite(big, ov)
d = ImageDraw.Draw(big)
for i, (oid, b, area, col) in enumerate(info):
    d.rectangle([b["left"] * scale, b["top"] * scale, b["right"] * scale, b["bottom"] * scale], outline=col + (255,), width=2)
    cx = (b["left"] + b["right"]) * scale // 2
    d.text((cx - 6, b["top"] * scale + 6), str(i + 1), fill=(255, 255, 255, 255))
d.rectangle([0, 0, 330, 30], fill=(0, 0, 0, 200))
d.text((8, 8), f"SAM 3.1 prompt 'shrimp': {len(masks)} objects", fill=(255, 255, 255, 255))
big.convert("RGB").save(out_path)
for i, (oid, b, area, col) in enumerate(info):
    print(i + 1, "id", oid, "box", b["left"], b["top"], b["right"], b["bottom"], "len_px", b["bottom"] - b["top"], "area_px", area)
