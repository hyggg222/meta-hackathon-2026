"""E2: measure each shrimp along its body, scale with the pasted card and ruler, flag overlapped shrimp."""
import json, sys
sys.path.insert(0, "/tmp/claude-1000/-home-huy-meta-hack-2026/011427c4-56d1-4559-82d5-a675d6376aa5/scratchpad/len")
from exp_ref import *

S_TRUE = 1.7
PICS_OUT = "/home/huy/meta-hack-2026/pics"
summary = {}
for photo in ("shrimpt", "shrimpt3"):
    canvas, ct, rt, _ = build(photo, S_TRUE, 0)
    p = f"{D}/raw/{photo}_s{S_TRUE}_r0.png"
    cv2.imwrite(p, canvas)
    shr = sam(p, "shrimp", f"{photo}_s{S_TRUE}_r0_shrimp")
    cm, _ = best(sam(p, "credit card", f"{photo}_s{S_TRUE}_r0_credit_card"), ct)
    rm, _ = best(sam(p, "ruler", f"{photo}_s{S_TRUE}_r0_ruler"), rt)
    kc = rect_sides(cm)[0] / CARD_MM[0]    # px per mm from the card
    kr = rect_sides(rm)[0] / RULER_MM[0]   # px per mm from the ruler
    # drop masks that are really the pasted card or ruler
    shr = [m for m in shr if iou(m, ct) < 0.3 and iou(m, rt) < 0.3]
    info = []
    for i, m in enumerate(shr):
        L, path, ta, tb, ha, hb = centerline(m)
        others = np.zeros_like(m)
        for j, o in enumerate(shr):
            if j != i:
                others |= o
        others = cv2.dilate(others.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        touch = False
        n = min(10, len(path) - 1)
        for tip, back, hw in ((path[0], path[n], ha), (path[-1], path[-1 - n], hb)):
            d = tip - back
            d = d / (np.linalg.norm(d) + 1e-9)
            tx, ty = tip + d * (hw + 1)          # point just beyond the end of the body
            disk = np.zeros(m.shape, np.uint8)
            cv2.circle(disk, (int(tx), int(ty)), 4, 1, -1)
            if (disk.astype(bool) & others).any() or tx < 3 or ty < 3 or tx > m.shape[1] - 4 or ty > m.shape[0] - 4:
                touch = True
        border = False
        info.append({"i": i, "L": L, "touch": touch or border, "path": path})
    med = float(np.median([x["L"] for x in info]))
    for x in info:
        x["short"] = x["L"] < 0.75 * med
        x["excluded"] = x["touch"]            # user rule: overlapped shrimp are reported, not counted
    ok = [x for x in info if not x["excluded"]]
    print(f"\n=== {photo}: scale from card {kc:.3f} px/mm (true {S_TRUE}), from ruler {kr:.3f} px/mm  ===")
    print(f"shrimp found {len(info)}, overlapped/excluded {len(info) - len(ok)}, measured {len(ok)}, median length {med:.0f}px")
    print(" #   length_px  by_card_mm  by_ruler_mm  true_mm(1.7px/mm)  status")
    for x in info:
        L = x["L"]
        print(f"{x['i'] + 1:2d}  {L:8.1f}  {L / kc:9.1f}  {L / kr:10.1f}  {L / S_TRUE:14.1f}   {'EXCLUDED (end touches another / border)' if x['excluded'] else 'ok'}{'  [short]' if x['short'] else ''}")
    if ok:
        arr = np.array([x["L"] for x in ok])
        print(f"measured shrimp: mean {arr.mean() / kc:.1f} mm by card, {arr.mean() / kr:.1f} mm by ruler (true-scale {arr.mean() / S_TRUE:.1f}); "
              f"card vs ruler differ by {100 * abs(1 / kc - 1 / kr) / (1 / kr):.2f}%")
    summary[photo] = {"n": len(info), "excluded": len(info) - len(ok), "kc": kc, "kr": kr}

    # picture
    sc = 3
    big = cv2.resize(canvas, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
    for x in info:
        m = shr[x["i"]]
        cnts, _ = cv2.findContours(cv2.resize(m.astype(np.uint8), None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        col = (120, 120, 120) if x["excluded"] else (60, 200, 60)
        cv2.drawContours(big, cnts, -1, col, 2)
        pts = (x["path"] * sc).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(big, [pts], False, (0, 0, 255) if not x["excluded"] else (160, 160, 160), 2)
        c = pts[len(pts) // 2][0]
        label = "overlap" if x["excluded"] else f"{x['L'] / kc / 10:.1f}cm"
        cv2.putText(big, label, (int(c[0]) - 25, int(c[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
        cv2.putText(big, label, (int(c[0]) - 25, int(c[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    for mm_, nm, k in ((cm, "card", kc), (rm, "ruler", kr)):
        cnts, _ = cv2.findContours(cv2.resize(mm_.astype(np.uint8), None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(big, cnts, -1, (255, 160, 0), 2)
        x0, y0 = cnts[0][0][0]
        cv2.putText(big, f"{nm} {k:.2f}px/mm", (int(x0) - 40, int(y0) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 160, 0), 2)
    cv2.imwrite(f"{PICS_OUT}/{photo}_length_result.png", big)
json.dump(summary, open(f"{D}/len_summary.json", "w"))
