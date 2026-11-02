import sys, json, requests
key = None
for l in open('/home/huy/meta-hack-2026/.env'):
    if l.startswith('META_API_KEY='):
        key = l.split('=',1)[1].strip().strip('"\'')
API = "https://api.meta.ai/v1"; H = {"Authorization": f"Bearer {key}"}
img, prompt, out = sys.argv[1:4]
r = requests.post(f"{API}/files", headers=H, files={"file": open(img,"rb")}, data={"purpose":"user_data"})
print("upload", r.status_code)
fid = r.json()["id"]
resp = requests.post(f"{API}/responses", headers=H, stream=True, json={
  "model":"sam-3.1",
  "input":[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","file_id":fid}]}],
  "stream":True,"metadata":{"mask_encoding":"one_bit"}})
print("resp", resp.status_code)
with open(out,"w") as f:
    for line in resp.iter_lines():
        if line: f.write(line.decode()+"\n")
