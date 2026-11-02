"""E1/E2: paste a bank-card-sized and a ruler-sized sprite of KNOWN pixel scale into real shrimp photos,
ask SAM for them, and compare the measured scale with the true one. Then measure shrimp with both references."""
import itertools, json, math, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/tmp/claude-1000/-home-huy-meta-hack-2026/011427c4-56d1-4559-82d5-a675d6376aa5/scratchpad/len")
from lib import *
from PIL import Image, ImageDraw

PICS = "/home/huy/meta-hack-2026/pics"
CARD_MM = (85.6, 53.98)
RULER_MM = (150.0, 30.0)
SS = 4


def sprite(kind, s, rot):
    """RGBA sprite at s px/mm, rotated by rot degrees. Returns array and alpha mask."""
    mm = CARD_MM if kind == "card" else RULER_MM
    w, h = int(round(mm[0] * s * SS)), int(round(mm[1] * s * SS))
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if kind == "card":
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(3.2 * s * SS), fill=(35, 70, 140, 255))
        d.rectangle([0, int(h * .14), w, int(h * .30)], fill=(15, 15, 15, 255))
        d.rectangle([int(w * .1), int(h * .42), int(w * .27), int(h * .6)], fill=(215, 175, 70, 255))
        for k in range(4):
            d.rectangle([int(w * (.1 + .2 * k)), int(h * .75), int(w * (.1 + .2 * k + .15)), int(h * .82)], fill=(230, 230, 230, 255))
    else:
        d.rectangle([0, 0, w - 1, h - 1], fill=(240, 215, 110, 255))
        for k in range(int(mm[0]) + 1):
            x = int(k * s * SS)
            ln = 0.30 if k % 10 == 0 else (0.20 if k % 5 == 0 else 0.12)
            d.line([x, 0, x, int(h * ln)], fill=(20, 20, 20, 255), width=max(1, int(SS * 0.5)))
        for k in range(0, int(mm[0]) + 1, 10):
            d.text((int(k * s * SS) + 3, int(h * .4)), str(k // 10), fill=(20, 20, 20, 255))
    a = np.array(im)
    if rot:
        c = (w / 2, h / 2)
        M = cv2.getRotationMatrix2D(c, rot, 1.0)
        cos, sin = abs(M[0, 0]), abs(M[0, 1])
        nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
        M[0, 2] += nw / 2 - c[0]
        M[1, 2] += nh / 2 - c[1]
        a = cv2.warpAffine(a, M, (nw, nh), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    a = cv2.resize(a, (a.shape[1] // SS, a.shape[0] // SS), interpolation=cv2.INTER_AREA)
    return a


def paste(canvas, spr, cx, cy):
    h, w = spr.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    alpha = spr[..., 3:4].astype(np.float32) / 255
    roi = canvas[y0:y0 + h, x0:x0 + w].astype(np.float32)
    canvas[y0:y0 + h, x0:x0 + w] = (roi * (1 - alpha) + spr[..., :3][..., ::-1] * alpha).astype(np.uint8)
    tm = np.zeros(canvas.shape[:2], bool)
    tm[y0:y0 + h, x0:x0 + w] = spr[..., 3] > 127
    return tm


def build(photo, s, rot):
    img = cv2.imread(f"{PICS}/{photo}.png")
    H, W = img.shape[:2]
    margin = 400
    canvas = np.pad(img, ((0, 0), (0, margin), (0, 0)), mode="edge")
    c, r = sprite("card", s, rot), sprite("ruler", s, rot)
    if rot == 90:
        ct = paste(canvas, c, W + 110, H / 2)
        rt = paste(canvas, r, W + 280, H / 2)
    else:
        ct = paste(canvas, c, W + margin / 2, H * 0.25)
        rt = paste(canvas, r, W + margin / 2, H * 0.72)
    return canvas, ct, rt, (H, W + margin)


def iou(a, b):
    u = (a | b).sum()
    return (a & b).sum() / u if u else 0


def best(masks, truth):
    sc = [iou(m, truth) for m in masks]
    if not sc:
        return None, 0
    i = int(np.argmax(sc))
    return masks[i], sc[i]


def run_case(args):
    photo, s, rot = args
    tag = f"{photo}_s{s}_r{rot}"
    canvas, ct, rt, shp = build(photo, s, rot)
    p = f"{D}/raw/{tag}.png"
    cv2.imwrite(p, canvas)
    res = {"photo": photo, "s": s, "rot": rot}
    for kind, truth, mm, prompt in (("card", ct, CARD_MM, "credit_card"), ("ruler", rt, RULER_MM, "ruler")):
        masks = sam(p, prompt.replace("_", " "), f"{tag}_{prompt}")
        m, sc = best(masks, truth)
        true_long = mm[0] * s
        tl, ts = rect_sides(truth)
        if m is None or sc < 0.5:
            res[kind] = {"found": False, "n": len(masks), "iou": round(sc, 3)}
            continue
        ml, ms = rect_sides(m)
        res[kind] = {"found": True, "iou": round(sc, 3), "n": len(masks), "long_px": ml, "true_long_px": true_long,
                     "err_pct": 100 * (ml - true_long) / true_long, "short_err_pct": 100 * (ms - mm[1] * s) / (mm[1] * s)}
    return res


if __name__ == "__main__":
    cases = list(itertools.product(["shrimpt", "shrimpt3"], [1.2, 1.7, 2.2], [0, 25, 90]))
    with ThreadPoolExecutor(4) as ex:
        out = list(ex.map(run_case, cases))
    json.dump(out, open(f"{D}/ref_results.json", "w"))
    print("photo     s    rot | card: found iou  long err% short err% | ruler: found iou long err% short err%")
    for r in out:
        def f(k):
            x = r[k]
            return f"{'yes' if x['found'] else 'NO ':>3} {x['iou']:.3f}  {x['err_pct']:+6.2f}  {x['short_err_pct']:+6.2f}" if x["found"] else f"NO  {x['iou']:.3f}  (n={x['n']})"
        print(f"{r['photo']:9s} {r['s']:.1f} {r['rot']:4d} | {f('card'):32s} | {f('ruler')}")
    for k in ("card", "ruler"):
        e = np.array([1e9 if False else abs(r[k]["err_pct"]) for r in out if r[k]["found"]])
        nf = sum(1 for r in out if not r[k]["found"])
        print(f"{k}: found {len(e)}/{len(out)}  mean abs long-side err {e.mean():.2f}%  worst {e.max():.2f}%")
