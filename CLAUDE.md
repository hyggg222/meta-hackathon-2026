# Shrimp size check: project context for coding agents

## What this is
Entry for the **Meta Global AI Developer Hackathon 2026, Indie Developer track** (solo).
Hard deadline: **01:00, 5 Nov 2026, Ireland time**; aim to submit before 22:00 on 4 Nov. New code only (written from 27 Oct); the repo is public.

A shrimp farmer lays about 10 shrimp flat next to a ruler and takes one phone photo. SAM 3.1 finds the shrimp and the ruler, code measures each shrimp along its body, and the app gives the size in shrimp per kg, the trend over samples, a stall flag and the cost of a day without growth. The farmer decides; the app never tells him to harvest.

The project replaced an earlier idea (a Werewolf game master). Its docs were removed on 1 Nov 2026; they stay in git history.

## Where things are
- Spec (draft until Charlie approves): `docs/spec/shrimp-size.md`. Read this first.
- Decisions and open questions: `docs/grill/shrimp-size.md`. Flow checklist: `docs/flow-c-checklist.md`. Terms: `GLOSSARY.md`.
- Hackathon rules and Meta API facts: `docs/meta-api.md`.
- `docs-private/`, `vids/`, `pics/`, `records/` and `.env` are local only and never published.

## Architecture (decided 1 Nov, in the ledger)
- **Python (FastAPI):** serves one static web page (a file input with capture, so no HTTPS is needed), calls SAM 3.1, measures lengths, applies the rules, stores samples in one SQLite file.
- **Node:** only `decode.mjs`, run as a subprocess, to decode SAM masks with `@meta-sam/parser`. Never use the PyPI package of that name.
- **Rules live in code** (length table, thresholds, cost of a stall day). Never let a language model decide a number or a flag. Muse Spark may only explain results by calling the rules, and it is optional.
- Test seams: measurement (masks in, lengths and flags out) and rules (table and thresholds in, size and flags out) are pure code, tested with synthetic masks of known length and no model client.
- Python is 3.8 on this machine (no `str.removeprefix`).

## Working conventions
- At least one real commit per day. Work in worktree branches, merge locally after checks pass; Charlie pushes main each evening. Never push, never add AI attribution to commits.
- Test first. Run the project's checks before saying done.
- Secrets live in `.env`; never print or commit them. Keep raw photos and video of people out of the repo.
- Evidence for the demo: an error table on at least 5 hand-measured trays, about 50 shrimp, with n stated (spec criterion 36). Say plainly what is demo data.
