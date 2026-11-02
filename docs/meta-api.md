# Hackathon rules and Meta API facts

Kept from the old dev brief (31 Oct 2026); only what the shrimp project still needs.

## Official rules, read on 2 Nov from the event page and the waiver
Sources: https://cerebralvalley.ai/e/meta-ai-developer-hackathon and its /waiver page (the Official Rules text).
- Judging weights (verified, not community numbers): Impact 30%, Use of Meta AI Tooling 25% ("beyond a basic integration, surfaced unexpected capabilities"), Technical Depth and Execution 20%, Demo 25% ("working, impressive demo", "holds up live", quality of the demo video). The Indie track page adds: judged on creativity, technical ambition, and whether it works.
- Submission goes through the Cerebral Valley portal (`.../hackathon/submit`). Due Nov 4, 9:00 PM ET (the waiver dates use EST, so this is 02:00 on 5 Nov in Ireland; the project keeps the stricter 01:00 limit). Judging Nov 4 to 8, winners Nov 9; bonus prizes announced about Nov 10.
- One track per participant and per project. Indie: individuals, students and teams up to four. Participants are 18 or older.
- The submission must be the entrant's own original work, with no other party holding rights in it; open source is allowed if its licence is followed. The entrant keeps ownership and grants the organizers a perpetual, worldwide, non-exclusive licence to use it. Anything shared at the event is not confidential.
- Not found in the public rules text (so unverified): the "new code only from 27 Oct" rule, a public repo requirement, a 3-minute video limit, and the bonus definitions. Check the submission form itself before the freeze.

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
