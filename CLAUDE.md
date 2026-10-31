# Moderator: project context for coding agents

## What this is
Entry for the **Meta Global AI Developer Hackathon 2026, Indie Developer track** (solo).
Hard deadline: **01:00, 5 Nov 2026, Ireland time**; aim to submit before 22:00 on 4 Nov. Feature freeze: evening of 2 Nov. New code only (written from 27 Oct); the repo is public.

**Moderator** is an AI game master for in-person Werewolf. No player holds a phone:
- **Camera phone** at the open end of a U layout, about 2 m high, tilted down. It streams frames to the server and plays narration audio.
- **Display phone** lies flat on the table centre. It shows seat numbers, role reveals and seer results to whoever is called.
- Players act with hand gestures: **finger count** (hold up the seat number) or the **sweep** to choose a seat, **raised hand** to confirm. Pointing is not the selector (measured: about 60 to 80% first try).

## Where things are
- Spec (approved): `docs/spec/moderator.md`. Read this first.
- Stack decision: `docs/adr/0001-stack.md`. Dev brief: `docs/dev-brief.md`. Decisions and measurements: `docs/grill/moderator.md`. Terms: `GLOSSARY.md`.
- `docs-private/`, `vids/`, `pics/` and `.env` are local only and never published.

## Architecture
- Two Next.js pages (camera, display), frames over WebSocket. No native app.
- **Python (FastAPI):** the game engine, local vision (MediaPipe pose and hands), the selector, the evaluation log.
- **Node (Next.js server):** Meta API gateway (SAM 3.1 calls and mask decoding with `@meta-sam/parser`; never the PyPI package of that name) and the narrator (Muse Spark text, optional LangChain.js, canned fallback lines).
- **Game engine:** a deterministic state machine. **Rules live in code; never let a language model decide rules or outcomes.** It has no model client and is tested with scripted events and no camera.
- SAM runs on snapshots only (about 1.5 s per image). MediaPipe runs on the live frames. Muse Spark text is always optional for the game to continue.
- Python is 3.8 or 3.9 on this machine (no `str.removeprefix`). MediaPipe 0.10.11 needs the no-dependencies install on 3.8.

## Game rules (decided)
- Demo roles first: Wolf, Seer, Villager. The engine is built so Bodyguard and Witch are added as data later.
- Night order: Wolves, then Seer. Every step has a random wait (20 to 35 s); dead roles are still called.
- Selector: finger count locks after 2 seconds steady; the sweep locks on a raised hand on the lit seat. A raised hand confirms dealing and the vote. No sound feedback.
- Wolves disagree or time out: nobody is bitten. Seer shows no choice in time: step skipped. Seer result shows WEREWOLF or NOT for 3 seconds.
- Day: discussion timer, then each living seat is named in turn (4 second window) and raised hands are counted per seat; a player's first raise counts. Tie: tied players defend 30 s each, re-vote; second tie kills nobody. Roles are not revealed on hanging.
- Gestures from dead or uncalled players are ignored.
- Wolves win when they are at least the rest; villagers win when all wolves are dead.

## Working conventions
- At least one real commit per day. Work in worktree branches, merge locally after checks pass; Charlie pushes main each evening. Never push, never add AI attribution to commits.
- Test first: the engine is slice 1. Run the project's checks before saying done.
- Secrets live in `.env`; never print or commit them. Keep friends' raw video and photos out of the repo.
- Evaluation for the demo: selector accuracy over at least 50 attempts per selector; night duration versus a human moderator and a pass-the-phone app.
- Pivot rule: if hand-raise and finger count (or the sweep) do not work from the camera, or the engine is not running by the end of 1 Nov, revisit the idea (see the ledger).
