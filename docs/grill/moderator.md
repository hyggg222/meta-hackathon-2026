# Grill ledger: Moderator

Flow C (solo personal project), hackathon time box. Dev facts: `docs/dev-brief.md`.

## Sources

- `docs-private/Moderator — Brief giải pháp cuối cùng (bản thị giác máy tính).md` (brief, 30 Oct)
- `docs-private/Moderator — Đặc tả tính năng.md` (feature spec, 30 Oct)
- `docs-private/01-hackathon-and-meta-models.md` (rules, model facts, SAM tests)
- `docs-private/04-brainstorm-archive.md` (rejected ideas, lessons)
- `docs-private/05-ideas-evaluation-and-prompt.md` (Gemini scores)
- `CLAUDE.md` (project context for agents)
- Not used: `/mnt/d/brightspace-quiz-simulator/docs` (a different project)

## Decisions

| Decision | Choice | Reason | Rejected |
| --- | --- | --- | --- |
| Project | Moderator, vision-based Werewolf game master | Decided 31 Oct after brainstorm | Thợ Cả, SpeakMate Live, Compass, RightBox, voice-only Moderator |
| Workflow | Flow C | Solo project | Flow A (team) |
| Rules in code | Game engine is a deterministic state machine; LLM never decides rules | One wrong ruling breaks the game | LLM-held game state (Gemini's idea) |
| Narration language | English | Decided in spec | Vietnamese |
| Devices | 2 phones, no laptop | Decided in spec | Laptop, second camera (cut) |
| Seating | Players sit around a square or rectangular table; horseshoe facing the camera is acceptable | Charlie, 31 Oct | Full circle on chairs |
| Camera and display position | U-shape of players around a table; camera at the open end, about 2 m high, tilted down; display phone flat on the table centre (not the floor) | All faces, hands and rays visible to one camera, so peek detection can work | Overhead above centre (hides eyes), full circle with outside camera (hides half the faces) |
| Keep or pivot | Keep Moderator (re-confirmed 31 Oct) | Nothing scored higher: Moderator ~23, Bench Scientist ~21, assembly coach ~21 (my estimates, noise about 4 points). Only Moderator needs masks that a plain LLM cannot give | Bench Scientist (toy, Meta models replaceable), assembly coach (frontier models already spot assembly mistakes), Thợ Cả, SpeakMate Live |
| Gate 1 test plan | Split: (a) solo geometry test, 15 points at numbered markers on chairs, about 1 h; (b) group photo with 4 friends, about 10 min, for SAM separation | Removes the need for 5 people to test | Testing with 5 people only |
| Gate 1 fallback | Cap tuning at 3 h; if under 12/15, use the seat-highlight sweep (display lights seats one by one, player raises a hand); pointing becomes a Should | Worst case is still a playable game | Second camera as a fix by default; switching idea |
| Camera count | One by default. Shoot a second phone on a long side at the same moment during the solo test (default, not yet confirmed); two cameras only if one fails and two pass | A second phone sees arm directions that are foreshortened for the first | Second camera from the start |
| Pivot checkpoint | Engine running by end of 1 Nov, otherwise revisit | Bounds the sunk time | |
| Scope | Accepted as in brief section 8. Must: setup, 5-role night, day vote with tie-break, peek warning, narration and music, summary with peek list, eval harness, debug overlay. Should: lie report, death card, personalized narration. Cut: second camera by default, themes, separate agent layer, other games | Peek warning is the video moment and the viral clip. The lie report is generated after the game from a transcript saved from day one, so it can wait | Lie report as Must (half a day of diarization risk), cutting death card and personalization too |
| Narrowed plan (31 Oct night, accepted) | Stay with Moderator. Selector is not pointing: use finger count (to be tested) or the sweep. Demo roles: Wolf, Seer, Villager first; Bodyguard and Witch are Should. Peek detection is a hard go/no-go, tested next together with raise-hand and finger count | Pointing alone gave 60 to 80% top-1 and about 80% top-2; the part that makes Moderator unique (peek detection) is still untested; no engine exists yet | Pivot now; keep pointing as the main selector; full 5-role Must |
| Peek (eye) detection dropped from Must | Charlie, 31 Oct night: skip eye detection, the selector is not even solved. Peek warning and peek list move to Should; if revived, use head direction | Keeps the remaining time on the selector, raise-hand and the engine. Cost, stated once: the peek clip was the planned viral moment and the main differentiator, so Most Viral chances drop and the video needs another memorable beat | Keeping it as the hard go/no-go |
| Pivot rule (agreed in advance, revised) | Pivot if hand-raise and finger count (or the sweep) do not work from the camera, or the engine is not running by the end of 1 Nov. Pivot target: Bench Scientist (solo-testable) | Bounds the sunk time | |
| Lock rule (two-way, set in the spec review) | Finger count locks after 2 seconds steady; the sweep locks on a raised hand on the lit seat; a raised hand still confirms dealing and the vote | A raised hand and a hand holding up fingers look alike, so one gesture cannot do both | Raised hand to lock a finger count |
| Day vote (two-way, set in the spec review) | Each living seat is named in turn (4 second window); raised hands counted per seat; a player's first raise counts, later ones ignored | Works without pointing; hands tie to seats through person masks | Simultaneous pointing then confirm (the brief's original) |
| Cuts for time (two-way, from the spec review) | Names by voice and voice commands move to Should; Must is 4 to 5 players (seat numbers 1 to 5, one hand); 6 to 8 players need two hands and are Should | Removes Voice Transcribe, name confirmation and mic echo from the critical path, and the two-hand counts | Keeping names by voice in Must |
| Commit path | Slices built in worktrees on branches; merged into local main after checks pass; Charlie pushes main once each evening (`! git push origin main`); no issues or PRs | Daily commits at about 2 min per day; the hook blocks agents from pushing main anyway | Issue + PR per slice (15 to 30 min each), pushing branches and merging on GitHub |
| Engine rule defaults | Adopt the 8 defaults in brief section 4 as config constants | Two-way door; each is one constant | |
| Seat identity across phases | Match new SAM masks to the previous seats by nearest centroid or IoU; if the mask count differs from the player count, redo the hand-raise seat check | Cheap, no 3D | Re-running the full setup every phase |
| Narration echo | Ignore the mic (no voice commands) while any audio plays | Cheapest fix; day discussion has no narration, so the transcript is unaffected | Echo cancellation |

## Open questions (in grill order)

1. TTS provider: listen to 3 samples when narration work starts (1 or 2 Nov), keep it behind one interface
2. Muse Image: reference-image support on the Meta API (test when Should work starts; keep or cut the death card)
3. Lie report: speaker-to-seat mapping through the setup name step is untested (diarization over the phone mic). Save the transcript from day one either way
4. ~~SAM image content type and latency~~ Verified 31 Oct with the Meta key: works, about 1.5 s per image. Still open: SAM on a real group photo (gate 1b needs 4 to 5 people), and whether the chair masks can give the seat map automatically (they found all 6 chairs plus the sofa on one still)

## Gate log

**Gate 1a, attempt 1 (31 Oct, about 18:00): not scorable, re-shoot.** `vids/CamA.MP4` (76 s, 1080p) and `vids/CamB.mp4` (91 s, 576p).
- The pose model found a person in 92% of Cam A frames, and arm lines were good for seats 2, 5 and 6 (for example 65 to 68 s, arm across the table).
- Only about 3 clear pointing holds exist, not 15, and there is no label list, so no hold can be scored against an intended target.
- Cam A is at about table-top height, so the table hides far-end hands and the far seats are tiny; the arm lines for the far-end seats (35 to 47 s) are wrong.
- Cam B is at about knee height behind chairs and sees almost nothing of the group. Unusable.
- The 3 h tuning clock has not started. It starts at the first scoring run on a valid shoot.

**Scratch scoring of the current Cam A video (31 Oct).** Rule: ray from elbow through index fingertip, nearest seat head position, excluding the pointer's seat. Marker positions read by hand from the empty frame. Result: inconclusive, no pass or fail.
- 5 holds detected: 2 are false positives (forearm resting on the table, 4 to 11 s); 3 are real pointing holds (60, 63 and 68 s), all from the near-right chair.
- Picks: seat 3, seat 4, seat 2, but the best-to-second-best margin is only 1 to 3 degrees and the best angle is 7 to 20 degrees off. Intended targets unknown, so none can be called right or wrong.
- Two ways of drawing the ray (elbow to index, shoulder to index) disagreed on 2 of the 3 holds, so the ray is noisy.
- Hypothesis to test in the re-shoot: neighbouring far-end seats (3 and 4) are only a few degrees apart as seen from the fingertip, about the same as normal human pointing error, so pointing alone cannot separate neighbours and the silent confirmation loop (or top-2 candidates) is essential. Three samples are not evidence; the 3 neighbour points in the re-shoot are.
- The pointer's seat was guessed from the nose position and was wrong (chair 6 read as 5). The real tool should take it from the seat masks.
- Overlay video (`vids/CamA_pose_overlay.mp4`, local only) shows the failure modes: the video holds 6 pointer positions of about 10 s each (5 targets, 2 hands); the camera sees only the near arm (the far arm is behind the body); a forearm resting on the table is read as pointing (8.5 s); the wrong arm was picked when both moved (18 s); when the fingertip overlaps a seat in the image the angle is unstable (45 s); far-end players are small and their arms are not extended in the image (28 s, 36 s). Good case: 7.5 s, arm clearly extended, seat 5 at 0 degrees and seat 6 only 4 degrees behind.

**Threshold or model? (31 Oct)** Holds found per visible arm per seat (expected 5): medium model at 960 px found 0 to 5; heavy model at full 1080p found 0 to 5, no better. So the model is not the main problem; the arm-extension rule is. A hand-landmark model on a crop around the hand finds the index fingertip on 50 to 88% of frames (hand 62 to 106 px wide), including far-end seats. Next: pointing = index extended, others curled; direction = knuckle to fingertip plus elbow to fingertip.
- Not tested: Meta's SAM 3D Body (open weights, 3D body and hand pose from one image; exists on GitHub and Hugging Face). It would fix 2D foreshortening and fits the snapshot-only design, but needs a GPU bigger than the local 4 GB card (Modal or Baseten credits) and speed is unknown. Candidate if the finger approach plateaus.

**Gate 1a, attempt 2 (31 Oct, `vids/CamA_2.MP4`, 30 s, camera higher, one pointer in seat 1, finger-based rule).** Still no pass or fail: intended targets not given.
- Hand found on 85% of arm frames (75% on the first video); pointing posture on 113 frames.
- The ray follows the finger well. Picks (seat marker positions estimated by hand, about 0.25 m above each chair-back digit): first pass 6, 4, 4, 5, 6; second pass 4, 4, 5, 6. Same order both times, so repeatable; accuracy unknown.
- Misses: no hand at 8.9 s (arm to the left, toward seat 2); seat 3 only flickers with 17 to 23 degrees off; so left and far-left targets are weaker.
- Neighbours 4 and 5 are only 1 to 5 degrees apart at times, so frame-by-frame picks flicker; take the median over the whole hold.
- Lesson: my first marker positions put seats 5 and 6 about 150 px too high and gave wrong picks. In the real game the seat positions must come from the SAM person masks, and the target should be the first mask the ray crosses, not an angle to a point.

**Lower thresholds and 3D (31 Oct).**
- Hand detection 0.3 to 0.1 with 3 crop sizes: hand found 84 to 90% (CamA_2) and 78 to 88% (CamA); pointing-posture frames 113 to 120 and 194 to 239. Helps, but the posture rule (index extended, others curled) is now the bigger limit: only about 44% of frames with a found hand count as pointing.
- The pick rule is weak: nearest angle to a point with no confidence and no minimum. Needed: median direction over the whole hold, a Gaussian likelihood per seat (sigma from measured noise, about 5 to 8 degrees), accept only if the top seat is clearly ahead, otherwise show the top 2 and confirm; and with SAM masks, take the first mask the ray crosses.
- MediaPipe's own 3D is not usable for direction: the shoulder-to-wrist depth component for the same kind of target flips sign between the right arm (-0.15 to -0.38) and the left arm (+0.24 to +0.42). The 2D image angle separated far-end targets (14 to 17 degrees) from across-the-table targets (-1 to 8 degrees) better, because the camera looks down.
- Options for real 3D, cheapest first: (a) ground-plane homography: use the 6 chair-back points as a metric top-down map, cast the pointing ray on that map; needs chair positions measured in cm; (b) SAM 3D Body on snapshots (Meta, open weights, GPU, accuracy for pointing untested); (c) two calibrated cameras and triangulation.

**Better hand models (31 Oct, CamA_2).**
- Hugging Face candidates: Meta Sapiens 2 pose (`facebook/sapiens2-pose-0.4b` to 5b): 308 keypoints with detailed hands, top-down (needs person boxes, SAM can give them), needs Python 3.12+ and torch 2.7+ (this machine has 3.8 and 3.9, a 4 GB GPU), license forbids surveillance and biometric uses, so read it before shipping. ViTPose+ has no hand keypoints. RTMPose-Hand (LiteRT) and WiLoR (3D hands) exist but are awkward to run here.
- SAM `hand` on all 306 sampled frames (265 s, about $0.80): a hand box matched the arm in 96% of arm-frames. So localising the hand is solved.
- MediaPipe Hands on the SAM box crop found landmarks on only 59% (the old pose-wrist crop: 94%), and pointing-posture frames stayed about 112. So the bottleneck is MediaPipe's hand keypoints (palm detector), not where the hand is. Lowering thresholds further has little left to give.
- Next candidates: (a) use the SAM hand mask itself for posture and direction (elongated mask, fingertip = far end), no keypoint model; (b) Sapiens2-0.4B hand keypoints (Python 3.12 install first).

**SAM-mask pointing on CamA_2 (31 Oct, `vids/CamA_2_sam_mask.mp4`).** SAM `hand` masks for fingertip and direction, SAM `chair` masks (from one still) as the seat map, no MediaPipe finger step.
- Hand mask matched the arm in 96% of arm-frames; pointing posture on 94 frames (MediaPipe finger rule: 113 to 120). Rule: mask length at least 78 px and tip width at most 0.52 of palm width; calibrated on only 8 pointing frames of one scene, so treat as untested elsewhere. Elongation did not separate pointing from resting hands.
- Misses: 8.8 s (matched the resting hand, not the pointing one) and 10.8 s (tip/palm 0.52, borderline).
- The mask outline of the pointing hand is clean and the fingertip is exact. The weak step is now the seat choice: "first chair mask the ray crosses" is biased to the chair nearest the fingertip in the image (13.2 s: seat 3, MediaPipe says 5), and chair bodies sit lower than seated heads, so rays toward near chairs (5, 6) pass above them. Needs person masks (the target is a person, not a chair) or a floor-plane map. With one person in the video this cannot be validated; gate 1b with 4 to 5 people can.

**Ground truth: 4 labelled stills (31 Oct, `pics/1to3..1to6.png`, local only), seat 1 pointing at seats 3, 4, 5, 6.** SAM `hand` and `chair` masks plus MediaPipe pose, 5 ray definitions x several target rules.
- The failure was my pipeline, not hand detection: finger axis from the SAM mask plus "chair body the ray crosses" (what the video used) got 0 to 1 of 4.
- "First chair crossed" best 2/4; "farthest crossed" best 3/4. The true seat is often in the middle of the crossed list (1to5 crosses 3, 4, 5, 6), so ordering cannot work.
- Best: forearm ray (elbow to wrist) aimed at the centre of a head zone above each chair (a rectangle about 0.7 chair-width wide and 0.5 chair-height tall above the chair back): 4/4, angle off 2 to 7 degrees, margin to the next seat 8 to 12 degrees. Elbow-to-fingertip aimed at the chair-back top also got 4/4 but with margins down to 0.9 degrees.
- Weak: finger axis (1 to 3 of 4) and eye/nose to fingertip (1 of 4), against my expectation from the pointing literature (from memory, not checked); the camera sees the head in profile.
- Caveat: n = 4; 2 of 15 combinations reached 4/4 and I picked them after seeing the results, so this is a lead, not a result. The head-zone rectangle is hand-defined; in the real game SAM person masks replace it. Needs a holdout: more labelled stills (1to2 is missing, and the other hand).

**Ten labelled stills (31 Oct, `pics/1to2..1to6` and `_r`, one pointer, seat 1).** The rule fixed in advance on the first 4 photos (forearm ray aimed at head-zone centre) was tested on 6 new photos.
- Bug found by looking at the overlay: arm selection (largest shoulder-to-wrist span) picked the resting near arm when the far arm pointed. Fixed by choosing the arm whose wrist is higher in the image. Before the fix the holdout was 1/6; after, 2/6 (6/10 overall).
- Every miss of that rule is one seat off (2 read as 3, 4 as 5, 5 as 6) except seat 2, which ranks 5th in both photos: chair 2 sits along the pointer's own side and is partly hidden behind them, so its mask and head zone are poor.
- Best combinations reach 7 to 8 of 10 top-1 (elbow-to-fingertip aimed at the chair-back top), but they were chosen after seeing all 10 photos, so the real accuracy is lower. Truth is within the top 2 for 8 of 10 in most combinations (the two misses are both seat 2).
- Reading: from one camera, pointing gives about 60 to 80% top-1 and about 80% top-2. It narrows to two seats and a confirm step must decide. The original bar (12 of 15 top-1, 80%) is not clearly met.
- Pending decision: pointing mode = top-2 plus silent confirm, with the gate rewritten as top-2 at least 90% on a fresh holdout of 15 or more photos from several pointers and seats; sweep stays the fallback.

**Can a Meta model replace MediaPipe? (31 Oct)**
- Muse Spark (`muse-spark-1.3`, hosted API, accepts images) asked to count extended fingers on 10 SAM hand crops of the pointing hand (true count 1): 7/10 correct, the 3 misses were small crops (87 to 125 px) returning 0; latency 1.3 to 7.9 s, median 2.8 s. Too slow and too uneven to replace a per-frame hand model; usable as a verifier at the lock moment (one call per decision).
- Sapiens 2 pose (Meta, open weights, hand keypoints): not run. Needs Python 3.12, torch 2.7+, its own demo scripts and a person detector, plus a GPU; try only if MediaPipe finger counting misses the 90% bar on the CamA_3 test.
- SAM masks (Meta API) can replace MediaPipe for hand localisation and, possibly, raise-hand geometry; finger counting from the mask alone is untested.
- Working split: SAM for seats, person and hand masks; MediaPipe Hands for fast finger reading; Spark as a verifier. MediaPipe is not a Meta model, so SAM and Spark must stay the visible, central parts in the demo.

**LangChain.js for learning (31 Oct, stack ADR pending).** The Meta API accepts OpenAI-style Chat Completions on `muse-spark-1.3` and strict JSON-schema structured output (tested with plain HTTP: 2.1 s and 2.7 s; not yet through LangChain.js itself). Candidate use: a narrator service in the Next.js server (prompt templates, Zod structured output, model swapped between Spark on the Meta API and Spark Open on a hosted provider), always with canned fallback lines so the game never waits on it. Not for the engine, vision, rules, or an agent layer.

**Open-weight prize (31 Oct).** The prize table in the brief and in the notes names Muse Glimmer or Muse Spark Open for "Best Build on Meta Open Weight Models" ($10K). Sapiens 2 is not on that list, so it would not qualify (official rules not seen; unverified). It would still count as a Meta open-weight model for round 1 and the tooling story. Spark Open is not on the Meta API; it runs through a hosted provider (Baseten, Modal, Fireworks) or self-hosted. Cheap way to target the prize: narration and summary text through Spark Open behind the narration interface. Needs provider credits, which Charlie has not confirmed.

**What runs where.** Meta Model API (the $150 credits) hosts Muse Wonder, Spark, Image, Voice Transcribe and SAM; open-weight models (for example SAM 3D Body) are not on the API and need a GPU. The event page says Modal gives $100 "to select participants" for open-weight models and lists no separate form; applications closed 25 Oct. How to claim is unverified.

**Re-shoot plan.** Layout seen in the video: seat 1 near-left, 2 left-far, 3 far-left, 4 far-right, 5 right-far, 6 right-near (chair numbers on the chair backs).
- Phone A at the open end as high as possible (at least 1.5 m, aim for 2 m), tilted down. Phone B on top of the fridge, about 1.7 m, looking across the table.
- One calibration still of the empty chairs from each phone.
- Per point: say "from to" aloud (for example "one to two"), point with a straight arm, hold 3 s, rest both hands on the table for 2 s.
- The 15 points, grouped by pointer:

| # | Pointer → target | Case |
|---|---|---|
| 1 | 1→2 | along the side, away |
| 2 | 1→4 | near to far |
| 3 | 1→6 | straight across |
| 4 | 2→3 | neighbour at the corner |
| 5 | 2→5 | straight across |
| 6 | 2→6 | across, toward camera |
| 7 | 3→1 | far to near |
| 8 | 3→4 | neighbour at the far end |
| 9 | 4→5 | neighbour at the corner |
| 10 | 4→6 | far to near |
| 11 | 5→1 | across, toward camera |
| 12 | 5→6 | along the side, toward camera |
| 13 | 6→2 | across, away |
| 14 | 6→3 | near to far |
| 15 | 6→5 | along the side, away |

## Flow C progress

- [x] 1. Idea (decided 31 Oct; stop criterion = gate 1a, fallback = sweep)
- [x] 2. Research (docs-private 01, 04; competitor claims in the brief are search-based, not exhaustive)
- [x] 3. Spec: approved 31 Oct (`docs/spec/moderator.md`)
- [ ] 4. Design: stack ADR written (`docs/adr/0001-stack.md`, status proposed, needs Charlie's OK); design-options for the display and camera pages still to do
- [ ] 5. Scaffold: this is slice S0 (skipped CI, labels, board, milestones, because 4 days; keep one check command and the repo layout)
- [x] 6. Backlog: 11 slices approved 31 Oct (spec, Slices heading); no issues or PRs, by decision
- [ ] 7. Each slice test-first (engine first)
- [ ] 8. Release: submission before 22:00, 4 Nov
- [ ] 9. Retro: after the event
