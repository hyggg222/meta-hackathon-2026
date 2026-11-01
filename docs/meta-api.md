# Hackathon rules and Meta API facts

Kept from the old dev brief (31 Oct 2026); only what the shrimp project still needs. Not verified: the official rules text, the rubric weights (30/25/25/20 come from community sources) and the bonus definitions.

## Event
- Meta Global AI Developer Hackathon 2026, Indie Developer track, solo.
- Deadline: 01:00, 5 Nov 2026 Ireland time. Target: submit before 22:00 on 4 Nov.
- New code only (from 27 Oct), public repo, 3-minute demo video, people in the video must consent, no raw photos or video in the repo, a Meta model must be central.
- Credits: $150 Meta API. SAM 3.1 costs $2.50 per 1,000 images, Voice Transcribe $0.18 per hour. Muse Spark price during the event is unknown.

## Scoring
Four equal criteria, 0 to 10 each: Impact, Use of Meta AI Tooling, Technical Depth and Execution, Demo. The top 5 per track are judged on the 3-minute video. Each Meta model must do something visible on screen, and depth is shown with numbers, not claims.

## Models
| Model | Known facts |
| --- | --- |
| SAM 3.1 | Text prompt only, one noun phrase per request. About 1.0 to 1.6 s per prompt, plus about 2 s to upload an image (do it once per image). It is shape-driven: "shrimp", "ruler" and "credit card" work, "card" returns nothing. |
| Muse Spark 1.3 | Multimodal, tool calling, structured output. |
| Voice Transcribe | `POST /v1/asr/transcribe` (WAV mono 16 or 24 kHz, max 10 min) and `wss .../asr/realtime`. Vietnamese is supported. |

## SAM 3.1 call
Output is text, one line per frame, with a box and a mask per object. The mask payload is base85 with a custom alphabet and needs the official decoder: the npm package `@meta-sam/parser` (`parseImageStream(...).finalResult`, `decodeMaskToRaster`). The PyPI package of the same name is an empty placeholder; never use it. Set `metadata.mask_encoding` to `one_bit` for small payloads.

```python
API = "https://api.meta.ai/v1"
H = {"Authorization": f"Bearer {API_KEY}"}
file_id = requests.post(f"{API}/files", headers=H, files={"file": open("frame.jpg", "rb")},
                        data={"purpose": "user_data"}).json()["id"]
resp = requests.post(f"{API}/responses", headers=H, stream=True, json={
    "model": "sam-3.1",
    "input": [{"role": "user", "content": [
        {"type": "input_text", "text": "shrimp"},
        {"type": "input_image", "file_id": file_id}]}],
    "stream": True, "metadata": {"mask_encoding": "one_bit"}})
# SSE: each line starts with "data: "
```
