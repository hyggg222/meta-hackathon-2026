import base64, json, math, os, subprocess, sys
sys.path.insert(0, "/tmp/claude-1000/-home-huy-meta-hack-2026/011427c4-56d1-4559-82d5-a675d6376aa5/scratchpad/pylib")
import cv2
import networkx as nx
import numpy as np
import requests
from skimage.morphology import skeletonize

D = "/tmp/claude-1000/-home-huy-meta-hack-2026/011427c4-56d1-4559-82d5-a675d6376aa5/scratchpad/len"
DECODE = "/tmp/claude-1000/-home-huy-meta-hack-2026/011427c4-56d1-4559-82d5-a675d6376aa5/scratchpad/sam/decode.mjs"
NODE_PATH = "/tmp/claude-1000/-home-huy-meta-hack-2026/011427c4-56d1-4559-82d5-a675d6376aa5/scratchpad/sam/node_modules"
KEY = None
for l in open("/home/huy/meta-hack-2026/.env"):
    if l.startswith("META_API_KEY="):
        KEY = l.split("=", 1)[1].strip().strip("\"'")
API = "https://api.meta.ai/v1"
H = {"Authorization": f"Bearer {KEY}"}


def sam(img_path, prompt, tag):
    """Call SAM 3.1, return list of full-size boolean masks (cached on disk)."""
    raw = f"{D}/raw/{tag}.txt"
    mj = f"{D}/raw/{tag}.json"
    img = cv2.imread(img_path)
    Hh, Ww = img.shape[:2]
    if not os.path.exists(mj):
        r = requests.post(f"{API}/files", headers=H, files={"file": open(img_path, "rb")}, data={"purpose": "user_data"})
        fid = r.json()["id"]
        resp = requests.post(f"{API}/responses", headers=H, stream=True, json={
            "model": "sam-3.1",
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt},
                                                   {"type": "input_image", "file_id": fid}]}],
            "stream": True, "metadata": {"mask_encoding": "one_bit"}})
        with open(raw, "w") as f:
            for line in resp.iter_lines():
                if line:
                    f.write(line.decode() + "\n")
        env = dict(os.environ, NODE_PATH=NODE_PATH)
        subprocess.run(["node", DECODE, raw, mj], check=True, env=env, capture_output=True,
                       cwd="/tmp/claude-1000/-home-huy-meta-hack-2026/011427c4-56d1-4559-82d5-a675d6376aa5/scratchpad/sam")
    out = []
    for m in json.load(open(mj)):
        b = m["bounds"]
        w, h = b["right"] - b["left"], b["bottom"] - b["top"]
        ras = np.frombuffer(base64.b64decode(m["b64"]), np.uint8).reshape(h, w)
        full = np.zeros((Hh, Ww), bool)
        full[b["top"]:b["bottom"], b["left"]:b["right"]] = ras > 0
        out.append(full)
    return out


def largest(mask):
    m = mask.astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n > 2:
        m = (lab == 1 + np.argmax(stats[1:, 4])).astype(np.uint8)
    return m


def centerline(mask, smooth=9):
    """Length along the body: skeleton longest path, smoothed, plus half-width at both tips.
    Returns (length_px, path_xy (N,2), tip_a, tip_b, halfwidth_a, halfwidth_b)."""
    m = largest(mask)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    sk = skeletonize(m > 0)
    ys, xs = np.nonzero(sk)
    idx = {(y, x): i for i, (y, x) in enumerate(zip(ys, xs))}
    G = nx.Graph()
    for (y, x), i in idx.items():
        G.add_node(i)
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            j = idx.get((y + dy, x + dx))
            if j is not None:
                G.add_edge(i, j, weight=math.hypot(dy, dx))
    comp = max(nx.connected_components(G), key=len)
    start = next(iter(comp))
    d1 = nx.single_source_dijkstra_path_length(G, start)
    a = max(d1, key=d1.get)
    d2, paths = nx.single_source_dijkstra(G, a)
    b = max(d2, key=d2.get)
    pts = np.array([(xs[i], ys[i]) for i in paths[b]], float)
    if len(pts) > smooth:
        k = np.ones(smooth) / smooth
        pad = smooth // 2
        padded = np.vstack([np.repeat(pts[:1], pad, 0), pts, np.repeat(pts[-1:], pad, 0)])
        sm = np.stack([np.convolve(padded[:, 0], k, "valid"), np.convolve(padded[:, 1], k, "valid")], 1)
        sm[0], sm[-1] = pts[0], pts[-1]
    else:
        sm = pts
    seg = np.hypot(*np.diff(sm, axis=0).T).sum()
    ha, hb = dt[int(pts[0][1]), int(pts[0][0])], dt[int(pts[-1][1]), int(pts[-1][0])]
    return seg + ha + hb, sm, pts[0], pts[-1], ha, hb


def rect_sides(mask):
    cnts, _ = cv2.findContours(largest(mask), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    (_, _), (w, h), _ = cv2.minAreaRect(c)
    return max(w, h), min(w, h)
