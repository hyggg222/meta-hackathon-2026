# Moderator: dev brief

Filtered from the brainstorm docs (31 Oct 2026). Only what is needed to build. Source docs stay in
`docs-private/` (not published). Items marked **(default)** were assumed, not decided; they are
config constants in the engine and can change at any time.

## 1. Frame

- **What:** an AI game master for in-person Werewolf. No player holds a phone. A camera phone watches
  the group; a display phone on the floor shows seat numbers; players point and raise a hand.
- **Event:** Meta Global AI Developer Hackathon 2026, Indie Developer track, solo.
- **Deadline:** 01:00, 5 Nov 2026 Ireland time (21:00 ET, 4 Nov). Target submit before 22:00, 4 Nov.
- **Feature freeze:** evening of 2 Nov. After that: eval, video, README, submission only.
- **Rules that shape the build:** new code only (from 27 Oct), public repo, 3-minute demo video,
  friends in the video must consent, no raw video in the repo, a Meta model must be central.
- **Resources:** $150 Meta API credits. Costs are small: SAM 3.1 $2.50 per 1,000 images, Voice
  Transcribe $0.18 per hour. Muse Spark price during the event is unknown.
- **Workflow:** Flow C (solo personal project) on a 4-day time box.

## 2. Scoring: what the build must show

Round 2 is four equal criteria, 0 to 10 each: Impact, Use of Meta AI Tooling, Technical Depth and
Execution, Demo. Top 5 per track are judged on the 3-minute video.

- Impact is the known weak spot (entertainment). Do not fight it in code; fight it in the video.
- Each Meta model must do something **visible on screen** (SAM masks, Spark's judgement frame,
  transcript). If MediaPipe does the main detection, SAM and Spark keep the visible jobs.
- Depth is proven by numbers (section 9), not by claims.
- Side prizes in reach: Most Viral ($20K, the peek-warning clip), Community Vote ($10K),
  Creative ($5K, only if the death card ships). Open Weight and Agentic are unlikely; do not build for them.

## 3. Product and hardware

| Device | Place | Job |
| --- | --- | --- |
| Camera phone | Open end of the U, about 2 m high, tilted down | Streams video and mic to the server; plays narration, music, effects |
| Display phone | Flat on the table centre | Seat numbers for confirmation, role reveal, seer result, timers. Dark when idle; low brightness at night |

- **Decided (31 Oct):** players sit in a U around a square or rectangular table, facing the camera.
  The docs said "floor" for the display phone; it is now the table. A full circle with one camera
  hides half the faces, and overhead hides the eyes.
- Both phones open a web page. No native app. The room stays lit ("night" is in the game only).
- Assumed: the camera phone speaker is loud enough; otherwise a Bluetooth speaker.
- Seats are numbered clockwise starting from the camera's left; use the same layout for every test photo.

## 4. Game rules (engine spec)

Roles: Werewolf, Villager, Seer, Bodyguard, Witch. Players choose the role set; the app blocks
nonsense sets (wolves >= everyone else) and suggests a default.

**Setup**
1. Pick role set on the display phone.
2. Assign seats: SAM 3.1 with prompt "person"; number seats clockwise; show the photo with numbers.
3. Names: "Seat N, say your name" -> Voice Transcribe -> the player raises a hand if the text is right.
4. Deal roles: shuffle; "Everyone, close your eyes"; call each seat, show the role for a few
   seconds, hand-raise to confirm, "Close your eyes".
5. Night 1: wolves open their eyes and see each other.
The camera records peeking during dealing too.

**Night** (fixed order; every step has a random wait, **(default)** 20 to 35 s)

| # | Role | Action | Display shows |
| --- | --- | --- | --- |
| 1 | Bodyguard | Point at who to protect (self allowed) | Pointed seat. Same person as last night: reject, show a cross |
| 2 | Werewolves | All living wolves point at one victim | Pointed seat; "not agreed" icon if they differ |
| 3a | Witch, save | Display shows the bitten seat (even if the potion is used). Raise hand = save | Victim seat |
| 3b | Witch, poison | Point at a target, or stay still to skip | Pointed seat |
| 4 | Seer | Point; after confirmation shows WEREWOLF or NOT for 3 s | Seat, then result |

- **Dead roles are still called** with the same random wait, so nothing leaks.
- Gestures from uncalled or dead players are ignored.
- Timeout without confirmation: Bodyguard and Seer skip; wolves disagree -> nobody is bitten **(default)**.
- Witch: one save, one poison, self-save allowed. Poison always kills; the Bodyguard does not stop it **(default)**.
- A bitten player survives if protected or saved.

**Day**
1. Announce deaths (never the cause). Check win conditions.
2. Discussion timer **(default)** 3 min; voice command "start voting" ends it early; "add one minute" extends it **(default)**.
3. "Three, two, one, point!": all living players point; one frame is captured and every ray is read.
4. For each player with at least one vote: "Votes for Minh, raise your hand." Final tally = hand-raises.
5. One vote each. If someone raises twice, count the round that matches their pointing ray; if neither matches, count the first **(default)**. Dead players' hands are ignored.
6. Most votes is hanged. Role is not revealed **(default)**.
7. Tie: each tied player defends for 30 s, then re-vote among them only. Second tie: nobody dies **(default)**.

**Win:** villagers when all wolves are dead; wolves when living wolves >= other living players.
Checked after every night and every vote.

**Silent confirmation loop (every night action):** point -> display shows the seat -> raise hand =
lock in, point elsewhere = change. No audio feedback.

**Peeking:** during any step, a player who is not being called and has open eyes triggers an
immediate anonymous warning (music stops, "Someone is peeking. Close your eyes.", floor screen
flashes red). Names and photos appear only in the end-of-game summary.

**Summary:** winner, all roles revealed, timeline of every night action, peek list (who, which
night, during which role's step, how many times), dramatic recap written by Spark.

## 5. Perception

| Gesture | Used for | Method |
| --- | --- | --- |
| Point | Night targets, votes | Pose landmarks: ray from elbow through index fingertip; pick the player mask nearest the ray. Ambiguous -> send the frame to Muse Spark |
| Raise hand | Confirm, witch save, vote confirm | Wrist above shoulder for at least 1 s |
| Eyes open or closed | Peek detection (dropped from Must 31 Oct, untested) | Face landmarks: eye-openness ratio, for players not being called |

- **Finger stage (tested 31 Oct on Cam A):** the pose model only gives a rough fingertip. Cropping around the pose wrist and running a hand-landmark model gave a clear index fingertip on 50 to 88% of frames, even for far-end players (hand about 60 to 100 px wide at 1080p). Plan: pointing = index finger extended with the other fingers curled; direction = knuckle to fingertip, combined with elbow to fingertip. The arm-extension threshold alone missed most real points.
- Seat identity: SAM 3.1 on a **snapshot** at setup and at the start of every phase. A gesture is
  assigned to the seat whose mask contains the wrist.
- SAM video is too slow (measured 26 Oct: 13.6 to 15 s for a 10 s clip), so SAM and Spark run only
  on snapshots at decision moments. Pose and eyes run continuously with a light model (MediaPipe).
- SAM is shape-driven, not purpose-driven ("power bank" failed, "black rectangle device" worked).
  "person" is a plain shape prompt, so this is low risk.

## 6. Architecture

- **Frontend:** Next.js/React, two pages (camera, display). WebSocket or WebRTC to the server.
- **Backend:** Python, FastAPI. Game engine = deterministic state machine. **Rules live in code;
  an LLM never decides rules or outcomes.**
- **Seam for tests:** vision produces events (`seat`, `gesture`, `time`); the engine only consumes
  events. The whole game, including the day vote and tie-break, can be tested with scripted events and
  no camera. This is where test-first work starts.
- **Narration:** Spark writes English lines per moment; TTS reads them; fixed command lines
  ("close your eyes", "point") are pre-recorded audio to avoid lag. TTS provider is undecided.
- **Audio:** night music runs all night (also masks movement noise); wolf howl, rooster at dawn,
  ticking clock in the last 10 s of discussion.

| Model | Job | Known facts |
| --- | --- | --- |
| SAM 3.1 | Seat identity, colored masks | API takes text prompt only, one phrase per request; $2.50 per 1,000 images |
| Muse Spark 1.3 | Resolve ambiguous pointing from a frame; narration; recap; lie report | Multimodal, tool calling, structured output |
| Muse Voice Transcribe | Setup names, voice commands, day transcript | Real-time STT; diarization (20+ speakers) only over native WebSocket; speaker labels reset each session; max session 60 min |
| Muse Image | Death card | Via aimlapi: text input only. Reference-image input on the Meta API is unverified |

SAM 3.1 call (from the playground "Get code"). **Verified 31 Oct:** `input_image` works; one still
takes about 1.0 to 1.6 s per prompt (upload about 2 s extra, do it once per frame). Output is text,
one line per frame, with a box and a mask per object (`<|box;...|><|mask;data=H,W,enc payload|>`).
The mask payload is base85 with a custom alphabet and needs the official decoder: npm package
`@meta-sam/parser` (`parseImageStream(...).finalResult`, `decodeMaskToRaster`). The PyPI package of the
same name is an empty placeholder (0.0.1); do not use it. Set `metadata.mask_encoding` to `one_bit` for
small payloads (the person mask was 750 chars instead of 54,000, same pixels). Tested prompts:
`person` (1 mask, exact outline), `hand` (both hands, the pointing finger visible in the mask),
`chair` (all 6 chairs, plus the sofa as a false positive), `pointing hand` (nothing: concept
prompts need plain nouns).

```python
API = "https://api.meta.ai/v1"
H = {"Authorization": f"Bearer {API_KEY}"}
file_id = requests.post(f"{API}/files", headers=H, files={"file": open("frame.jpg", "rb")},
                        data={"purpose": "user_data"}).json()["id"]
resp = requests.post(f"{API}/responses", headers=H, stream=True, json={
    "model": "sam-3.1",
    "input": [{"role": "user", "content": [
        {"type": "input_text", "text": "person"},
        {"type": "input_image", "file_id": file_id}]}],
    "stream": True, "metadata": {"mask_encoding": "lossless"}})
# SSE: each line starts with "data: "
```

## 7. Feasibility gates (31 Oct, run first)

| Gate | Pass |
| --- | --- |
| 1a. Pointing geometry (solo) | 6 to 8 numbered markers at head height on chairs in the U. You sit in different seats and point: 15 points covering across-table, same side along the axis, far to near, near to far, adjacent neighbours. Pass: at least 12 of 15; log each miss as occlusion, ambiguous ray or bad landmarks |
| 1b. SAM on a group | One photo of 4 to 5 friends in the U layout, prompt "person": every player separated |
| 2. Hand and eyes | Raised hand vs squinting eye on 10 test images: at most 1 error |
| 3. Independent review | Done 30 Oct (Gemini 24/40, no "change idea" verdict). Treat as passed |

- Also measure: SAM latency on one still image; whether the camera sees the eyes and hands of 5 to 8 players.
- Camera: phone A at the open end, about 2 m high, tilted about 40 degrees. Optionally shoot every test point at the same moment with phone B on a long side (costs almost nothing). One camera if A passes; two only if A fails and A+B passes.
- **Fallback (decided 31 Oct):** tune for at most 3 h. If still under 12 of 15, use the seat-highlight sweep: the display lights seats one by one and the player raises a hand on the target. Pointing becomes a Should.
- **Checkpoint:** engine running by the end of 1 Nov, otherwise revisit the idea.
- **Hard go/no-go (31 Oct, revised):** raise-hand (9 of 9) and finger count (at least 90% for 1 to 5 from a near and a far seat) must work from the camera. Capture: `vids/CamA_3.MP4`, same camera position as CamA_2. Eye detection is out of scope. If both selectors fail, pivot (ledger).

## 8. Scope

**Must (core loop plus the two moments the video needs)**
- Setup: role set, SAM seats, names by voice, role dealing
- Night with 3 roles first (Wolf, Seer, Villager; the engine keeps all 5), silent confirmation, random waits, dead roles still called
- Target selector: finger count (hold up the seat number, palm to the camera, two hands for 6 to 8) or the sweep; pointing is not the selector (31 Oct tests: about 60 to 80% top-1, about 80% top-2 from one camera)
- Day: timer, simultaneous vote, hand-raise confirmation, tie-break
- English narration, music, effects
- Summary: timeline of night actions
- Eval harness (section 9)
- Debug overlay on the camera view (masks, pointing rays). Needed for the split-screen video; cheap if built with the vision code

**Should (only after Must runs end to end)**
- Bodyguard and Witch roles; pointing with a top-2 confirm as an upgrade to the selector
- Peek warning (dropped from Must on 31 Oct: eye detection was untested and the selector is not solved; if revived, try head direction instead of eye openness)
- Lie report from the day transcript (needs speaker to seat mapping, section 10)
- Death card with Muse Image
- Personalized narration from daytime snapshots

**Cut or vision-only**
- Second camera, story themes, a dedicated agent layer, other games (Mafia, Avalon). Mention "next: any in-person group game" in the video only
- Clips for X are production work on 4 Nov, not features

## 9. Evaluation to produce (Depth evidence)

1. Pointing accuracy over at least 50 points vs the intent the player confirmed.
2. Peek detection vs labels a human assigns by watching the video.
3. Night duration: Moderator vs a human moderator vs a pass-the-phone app.

Log every decision snapshot, ray, chosen seat and confirmed seat from day one so these numbers
come free from the play-tests.

## 10. Gaps found in the source docs (decide or test before building)

1. ~~Camera and seating geometry~~ Resolved 31 Oct: U-shape around a table, tilted camera (section 3).
2. ~~No fallback if gate 1 fails~~ Resolved 31 Oct: 3 h tuning cap, then the sweep (section 7).
3. ~~Seat identity across phases~~ Decided 31 Oct: match new masks to previous seats by nearest centroid or IoU; redo the hand-raise seat check if the count differs.
4. **Lie report needs "who said it".** Diarization labels are not seats, and reset per session.
   Idea: use the setup step ("Seat N, say your name") to map label to seat in the same session. The whole
   game must fit in 60 min, or re-enroll.
5. ~~Speaker echo~~ Decided 31 Oct: ignore the mic for commands while any audio plays.
6. **Latency is unmeasured.** The confirm loop must show the seat in about 1 s. Do it from local pose
   plus cached masks; SAM and Spark only on ambiguity.
7. **Peek false positives** (head down, glasses, dim face) are untested. Tune on the labelled video.
8. ~~How a commit reaches main~~ Resolved 31 Oct: worktree branches, local merge after checks, you push main each evening.
9. **Housekeeping.** `docs-private/` was not ignored (now excluded locally). `CLAUDE.md` and
   `README-docs.md` point to files that do not exist under those names.

## 11. Schedule

| Day | Goal | Done when |
| --- | --- | --- |
| 31 Oct | Gates 1 to 3; engine with 5 roles as a CLI with scripted events | Gate numbers recorded; one simulated game runs in a terminal |
| 1 Nov | Camera and display pages; point, raise hand, silent confirm; full night | Play-test a night with 3 to 5 people |
| 2 Nov | Day vote, tie-break, narration, music; summary; peek warning. **Freeze in the evening** | One full game with friends |
| 3 Nov | Eval of 50+ points and peek labels; film a real game; edit | Eval table and a draft video under 3 min |
| 4 Nov | Final video, README, submission text; post the clip on X; **submit before 22:00** | Submitted |

At least one real commit per day.

## 12. Video beats the build must support (3 min)

0:00 overhead view, SAM masks on five people, "no one is holding a phone" -> 0:10 pain point in one
line -> 0:20 to 1:20 real game, split screen (room vs the AI's view), point, floor screen, raise hand
-> **1:20 memorable beat: open** (the peek moment is dropped; candidates: the silent night choice read from
finger count with the SAM hand mask on screen, or the lie report; also the standalone 15 s clip for X) -> 1:40 dawn, death card, day vote -> 2:05 summary and lie report -> 2:30 diagram
and eval table -> 2:50 the former moderator sits in the circle, "next: any in-person group game".

## 13. Dropped on purpose

Rejected ideas and why (Compass, RightBox, Thợ Cả, SpeakMate Live, others), competitor detail
(Werewolf: Party Game Narrator, Bezier, Wolfia, Telegram bots; keep for the README and pitch only),
Gemini score history and the re-grading prompt, winning-project patterns, personal background,
and the Meta cookbook inventory. All of it is in `docs-private/04-*` and `05-*`.
