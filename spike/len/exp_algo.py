"""E3: does the centerline-length algorithm recover a known length on synthetic curved bodies (no SAM)?"""
import math, sys
sys.path.insert(0, "/tmp/claude-1000/-home-huy-meta-hack-2026/011427c4-56d1-4559-82d5-a675d6376aa5/scratchpad/len")
from lib import *

rng = np.random.default_rng(0)
rows = []
for arc in (120, 250):
    for R in (60, 100, 200, 400, 1e6):          # curvature: small R = strongly curled
        if arc / R > 5.5:
            continue
        for r0, r1 in ((18, 8), (10, 5)):         # half-width head -> tail
            for noise in (0, 1):
                S = 4
                size = int(max(2 * min(R, 800) + 100, arc + 120)) if R < 1e5 else arc + 120
                size = min(size, 900)
                canvas = np.zeros((size * S, size * S), np.uint8)
                phi = arc / R
                cx, cy = size * S / 2, size * S / 2 - (R * S if R < 1e5 else 0) * 0
                ts = np.linspace(0, 1, 3000)
                for t in ts:
                    ang = -phi / 2 + phi * t
                    if R < 1e5:
                        x = cx + R * S * math.sin(ang)
                        y = cy + R * S * (1 - math.cos(ang)) - R * S * (1 - math.cos(phi / 2)) * 0.5
                    else:
                        x = cx - arc * S / 2 + arc * S * t
                        y = cy
                    r = (r0 + (r1 - r0) * t) * S
                    cv2.circle(canvas, (int(round(x)), int(round(y))), int(round(r)), 255, -1)
                m = cv2.resize(canvas, (size, size), interpolation=cv2.INTER_AREA) > 127
                if noise:
                    n = cv2.GaussianBlur(rng.random(m.shape).astype(np.float32), (0, 0), 2.0)
                    bl = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.0)
                    m = (bl + (n - n.mean()) * 1.2) > 0.5
                true = arc + r0 + r1
                L, *_ = centerline(m)
                rows.append((arc, R, r0, noise, true, L, 100 * (L - true) / true))

print("arc  R     halfw0 noise  true_px  measured_px  err%")
for r in rows:
    print(f"{r[0]:4d} {('flat' if r[1] > 1e5 else int(r[1])):>5} {r[2]:5d} {r[3]:5d}  {r[4]:7.1f} {r[5]:10.1f} {r[6]:6.2f}")
errs = np.array([r[6] for r in rows])
print(f"\nN={len(errs)}  mean err {errs.mean():+.2f}%  mean abs {np.abs(errs).mean():.2f}%  worst {errs[np.abs(errs).argmax()]:+.2f}%")
