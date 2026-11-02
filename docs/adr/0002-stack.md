# ADR-0002: Python FastAPI core with one Node script to decode SAM masks

Date: 2026-11-01
Status: accepted

## Context
Solo build with three days. Rules (length table, stall flag, cost of a stall day) must be code, never a language model. SAM 3.1 returns masks in a custom format; the only decoder is the npm package `@meta-sam/parser` (the PyPI package of the same name is an empty placeholder). The length-along-the-body method from the spike is Python (scikit-image, networkx). This machine has Python 3.8. The farmer's phone only needs to take a photo; the history must be shared between phone and laptop.

## Decision
- **Python (FastAPI):** serves one static web page, calls SAM 3.1, measures lengths, applies the rules, and stores samples in one SQLite file (photos beside it, git-ignored).
- **Node:** only `decode.mjs`, run by Python as a subprocess, to decode the SAM mask payload.
- **Page:** a file input with the capture attribute opens the phone camera, so no HTTPS and no getUserMedia. The phone opens the laptop over the local network.
- **Data files:** the length table, the stall threshold and the harvest size are config or data files that can be replaced without code changes.
- **Tests:** pytest on pure code (measurement with synthetic masks of known length, rules); ruff for lint.

## Alternatives
- FastAPI plus a Next.js server (the Werewolf stack): two servers to run and debug for a page this small; the gain is nicer UI tooling the demo does not need.
- All TypeScript: one runtime, but the length algorithm must be ported to JavaScript, which costs a day and may change the measured error.
- JSON file or browser localStorage instead of SQLite: a JSON file breaks on concurrent writes and cannot query by day; localStorage cannot share history between phone and laptop.

## Consequences
- Two runtimes (Python 3.8 and Node), but only one long-running process.
- The measurement and rules modules have no model client, so they are tested without network or camera.
- A subprocess call per photo adds some startup time; the target is under 10 seconds from photo to result (spec criterion 7), so measure it in slice 0.
- No HTTPS means the page works only on the local network; a public demo link is out of scope.
