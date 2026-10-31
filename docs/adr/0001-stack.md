# ADR-0001: Python engine and vision, Node gateway for Meta models, two phone web pages

Date: 2026-10-31
Status: proposed

## Context
Solo build, freeze on the evening of 2 Nov. Two phones must work from a browser. Rules must be code, never a language model. SAM 3.1 returns masks in a custom format; the official decoder is the npm package `@meta-sam/parser`, and the PyPI package of the same name is an empty placeholder. MediaPipe works in Python. Narration must never block the game.

## Decision
- **Phones:** two Next.js pages (camera, display). The camera page sends JPEG frames to the server over a WebSocket and plays server audio. No WebRTC, no native app.
- **Python (FastAPI):** the game engine (pure state machine, no model client), local vision (MediaPipe pose and hands: raise-hand, finger reading), the selector, the evaluation log.
- **Node (the Next.js server):** the gateway to the Meta API: SAM calls and mask decoding with `@meta-sam/parser`, and the narrator (Muse Spark text). The narrator may use LangChain.js (prompt templates, Zod structured output, swappable model) as a learning goal; it must fall back to canned lines when a call fails or is slow.
- **Talk between them:** HTTP on localhost. The engine emits commands (speak, show, play); the Node side returns text and masks.
- **Audio:** fixed command lines pre-recorded; narration lines through one TTS interface (provider chosen later).
- **Python:** 3.9 if MediaPipe installs cleanly, otherwise 3.8 with the no-dependencies install used on 31 Oct.
- **Demo runs on a laptop** on the local network; phones connect over an HTTPS tunnel or a local certificate, because phone browsers only allow the camera on secure pages.

## Alternatives
- **All Python, call the Meta API directly:** no usable mask decoder in Python, and the decoding format is not documented; porting it costs time we do not have.
- **All TypeScript, engine included:** the engine and MediaPipe are stronger in Python and match the builder's skills.
- **WebRTC video streaming:** more setup and sync work; the selector and raise-hand need frames, not a live stream.
- **LangChain.js required:** it adds a second runtime and an abstraction; it stays optional so removing it only means calling the API with fetch.

## Consequences
- Two processes to start and debug; one more hop between engine and Meta calls.
- The engine stays testable with scripted events and no camera or network.
- Phone camera over HTTPS is a day-one risk: test it in the first slice.
- Meta models keep the visible jobs (SAM seats, person and hand masks, Spark text); MediaPipe is not a Meta model, so the demo must show the SAM overlay.
- Swapping narration to Muse Spark Open on a hosted provider is one setting, if credits exist.
