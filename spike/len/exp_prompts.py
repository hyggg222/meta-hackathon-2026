import sys
sys.path.insert(0, "/tmp/claude-1000/-home-huy-meta-hack-2026/011427c4-56d1-4559-82d5-a675d6376aa5/scratchpad/len")
from exp_ref import *

photo, s, rot = "shrimpt3", 1.7, 0
canvas, ct, rt, _ = build(photo, s, rot)
p = f"{D}/raw/{photo}_s{s}_r{rot}.png"
cv2.imwrite(p, canvas)
for prompt in ["card", "credit card", "bank card", "blue card", "blue rectangle", "rectangle", "plastic card", "blue credit card"]:
    masks = sam(p, prompt, f"prm_{prompt.replace(' ', '_')}")
    m, sc = best(masks, ct)
    print(f"{prompt:18s} n={len(masks):2d}  best IoU with pasted card = {sc:.3f}")
