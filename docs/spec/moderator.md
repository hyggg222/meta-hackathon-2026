# Moderator: spec

Status: approved by Charlie, 31 Oct 2026 (spec and slices). Stack: `docs/adr/0001-stack.md` (proposed).

Sources: `docs/grill/moderator.md` (decisions, gate log), `docs/dev-brief.md` (rules, perception, schedule), `GLOSSARY.md` (terms).

## Problem and users
Werewolf played in person needs a moderator who cannot play, or a phone passed around the table that slows the game and leaks information. Moderator is an AI game master: a camera phone watches the players, a display phone shows what only the called player is meant to see, and players act with hand gestures. First users: Charlie and friends, 4 to 5 players, in the U layout.

## Scope
**In (Must)**
- Setup: role set (nonsense sets blocked, a default suggested), seats from SAM person masks counted clockwise, "Seat N" as the names, role dealing with raise-hand confirmation.
- Night with Wolf, Seer, Villager; random waits; dead roles still called.
- Selector for choosing a seat: finger count if its test passes, otherwise the sweep. Silent confirmation on the display phone.
- Day: discussion timer, per-candidate raise-hand vote, tie-break, win conditions.
- English narration (Spark text, TTS voice), music, effects. Summary with the timeline of night actions.
- Evaluation log and report, baseline timings, debug view for the demo video.
- 4 to 5 players (seat numbers 1 to 5, one hand).

**Should (only after Must runs end to end)**
Bodyguard and Witch; 6 to 8 players (two-hand counts); names and voice commands by voice (Voice Transcribe); lie report; peek warning by head direction; pointing with top-2 confirm; death card; personalized narration; narration text through Muse Spark Open (hosted) to target the open-weight prize.

**Out:** second camera, themes, a separate agent layer, other games, native app. No raw video or photos of people in the repository; friends in the video must consent.

## Acceptance criteria
1. Given 4 to 5 players in the U layout, when setup runs, then each gets a distinct seat counted clockwise and the display phone shows the photo with numbers. A role set with wolves at least the rest is refused and a default is suggested.
2. Given roles are dealt, when a seat is called, then its role shows on the display phone only during that step and is cleared when the step ends; the deal moves on after that player's raised hand.
3. Given a night step with finger count, when the called player holds up a number, then the display phone shows that seat within 3 seconds, with no sound; holding it 2 seconds locks it; a different number replaces it.
4. Given a night step with the sweep, when seats light one by one, then a raised hand locks the lit seat, with no sound.
5. Given the wolves disagree or time runs out, then nobody is bitten; given the Seer chooses nothing in time, then the step is skipped.
6. Given a dead role, when its step comes, then it is still called with a random wait of 20 to 35 seconds.
7. Given a gesture from an uncalled or dead player, then it is ignored.
8. Given the Seer locked a seat, then the display phone shows WEREWOLF or NOT for 3 seconds.
9. Given the day vote, when each living seat is named in turn (4 second window), then raised hands are counted per seat; a player's first raise counts and later raises are ignored; dead players are ignored.
10. Given a tie, then each tied player defends for 30 seconds and a re-vote runs among them; a second tie kills nobody.
11. Given any night or vote, when wolves are all dead or at least the rest, then the game ends with the correct winner. The same event list always gives the same result, and the engine depends on no model client.
12. Given each key moment (night falls, dawn, death, hanging, end), then an English line is spoken, fixed command lines are pre-recorded, and music plays all night.
13. Given the game ends, then the display shows the winner, every role and the timeline of each night's actions.
14. Given the debug view is on, then the camera page shows the seat masks and the read number.
15. Given any selection, then the log records the time, the read seat and the seat the player keeps after silent confirmation; the report gives accuracy per selector over at least 50 attempts each.
16. Given a night, then its duration is logged; a human moderator night and a pass-the-phone night are each timed once for comparison.

## Test seams
- **Game engine:** events in (seat, choice, time), commands out (speak, show, play). Pure code, tested with scripted events and no camera. Starts first.
- **Selector:** finger count is a snapshot in, a seat and a confidence out, tested on labelled stills. Sweep is a light schedule plus raised-hand events in, a locked seat out, tested with scripted events.
- **Evaluation:** logs in, metrics out.

## Decisions
- Stay with Moderator, narrowed plan and pivot rule: `docs/grill/moderator.md`.
- Selector is not pointing (about 60 to 80% first try, about 80% top 2 from one camera): same file, gate log.
- Eye and peek detection dropped from Must: same file.
- Finger count locks after 2 seconds steady; the sweep locks on a raised hand; the confirmation by raised hand stays for dealing and the vote (two-way, added to the ledger).
- Day vote is per-candidate raise-hand with a first-raise rule (two-way, added to the ledger).
- Names by voice and voice commands cut from Must; 4 to 5 players (two-way, added to the ledger).
- Worktree branches, local merge, Charlie pushes main each evening; camera at the open end of the U with the display phone on the table: same file.
- Seat map and hand localisation from SAM masks (tested on one person), finger reading from a hand-landmark model: `docs/dev-brief.md`.

## Risks and open questions
- Finger count is untested. Go/no-go: at least 90% for 1 to 5 from a near and a far seat, and raise-hand 9 of 9. If it fails, the sweep ships; if both fail, pivot to Bench Scientist.
- Engine running by the end of 1 Nov (one full night from scripted events plus a live selector), or the idea is revisited.
- Hands must be tied to seats through person masks; untested on 4 to 5 real people.
- Latency: SAM is about 1.5 s per image plus upload; the 3 second bound in criterion 3 is not yet measured end to end.
- Without the peek moment the video needs another memorable beat; Most Viral chances are lower.
- Open: TTS provider (listen to 3 samples, keep behind one interface); Muse Image reference-image support.

## Slices
Order: slice 0 first, then the rest by their Blocked by lists. Slices with no shared blockers can be built in parallel worktrees. Delivery checkpoint (end of 1 Nov): slices 0, 1, 3, 4 and 5 working together, meaning one full night on the phones with the sweep.

**S0. Two phones talk to the server.** The camera page sends frames to the server over a WebSocket; the display page shows a message sent by the server; both phones reach the laptop over an HTTPS tunnel or local certificate. Includes the project checks (engine tests, web tests, lint, format) in one command. Criteria: none (enabling). Blocked by: none.

**S1. Night plays to a winner from scripted events.** The engine runs setup, a night with Wolf, Seer, Villager, random waits, dead roles still called, ignored gestures, wolf disagreement, Seer skip and Seer result, then the win check; a scripted game plays in a terminal. Interfaces: events in, commands out. Criteria: 5, 6, 7, 8, 11 (night side). Blocked by: S0.

**S2. Day vote and tie-break in the engine.** Discussion timer, per-candidate vote with the first-raise rule, hanging, tie defence and re-vote, second tie, win check after a vote; a scripted full game with several days plays to the end. Criteria: 9, 10, 11 (day side). Blocked by: S1.

**S3. Seats from the camera.** At setup, SAM person masks (through the Node gateway and the official mask decoder) give each player a seat counted clockwise; the display page shows the photo with the numbers; the role set is checked and a nonsense set refused with a default suggested. Criteria: 1. Blocked by: S0.

**S4. Raised hand per seat, and role dealing.** Live frames give a raised hand per seat (wrist above the shoulder, steady, tied to a seat through its mask); the engine receives the event; the display deals roles one seat at a time, shows each only during that step, and moves on after the raised hand. Criteria: 2. Blocked by: S1, S3.

**S5. Night on the phones with the sweep.** The display lights seats one by one, a raised hand locks the lit seat, the night plays on the real phones with the Seer result shown for 3 seconds. This is the fallback selector and defines the selector interface. Criteria: 4, 8 (display side). Blocked by: S1, S3, S4.

**S6. Finger count selector.** Live frames give the number of fingers held up (palm to the camera); the display shows the read seat within 3 seconds, a 2-second steady hold locks it, another number replaces it; it plugs into the selector interface and is checked on labelled stills (1 to 5, near and far seat). Criteria: 3. Blocked by: S5 and a pass on the CamA_3 test (at least 90%).

**S7. Day vote on the phones.** Each living seat is named in turn with a 4-second window, raised hands are counted per seat, and the hanging, tie-break and win happen on the real phones. Criteria: 9, 10 (real setup). Blocked by: S2, S4.

**S8. Narration, music and effects.** For each key moment the engine emits a speak command; the Node narrator returns an English line (Spark text, canned fallback if slow or failing), a TTS interface speaks it, fixed command lines are pre-recorded, and night music plays all night. Criteria: 12. Blocked by: S0, S1.

**S9. Summary and debug view.** The display shows the winner, every role and the timeline of each night's actions; the camera page can overlay seat masks and the read number for the demo video. Criteria: 13, 14. Blocked by: S2, S3.

**S10. Evaluation log and report.** Every selection is logged (time, read seat, kept seat, selector); a report gives accuracy per selector over at least 50 attempts; night duration is logged, with baseline timings of a human moderator and a pass-the-phone night noted. Criteria: 15, 16. Blocked by: S5.

Coverage: criteria 1 to 16 are each covered (1: S3; 2: S4; 3: S6; 4: S5; 5, 6, 7: S1; 8: S1, S5; 9: S2, S7; 10: S2, S7; 11: S1, S2; 12: S8; 13, 14: S9; 15, 16: S10).
