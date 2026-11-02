# ADR-0003: The farmer uses a Messenger bot; the web page becomes a read-only dashboard

Date: 2026-11-02
Status: accepted (approved by Charlie on 2 Nov)

## Context
The web page for taking a photo, choosing shrimp and saving looked bad and was hard to use. A farmer already chats on a phone, so sending a photo to a bot and reading a reply is a smaller step. About two days remain before the freeze. Messenger works for admins, developers and testers of a Meta app without app review; Zalo needs an Official Account whose terms for an individual are not verified. The judging weights Meta AI tooling (25%) and the demo (25%).

## Decision
- The bot is a Messenger bot: the farmer sends the tray photo and gets a reply photo (outlines, body lines, numbers, lengths) and a Vietnamese text. The sample is saved only after the farmer says yes; numbers in a reply choose which shrimp count.
- The server keeps the same pipeline and rules (SAM, measurement, size table, flags). The default choice of shrimp is the current overlap rule plus a minimum length of 50 mm (a setting).
- The web page stays as a read-only dashboard plus feed entry and setup. The Photo screen is removed.
- Muse Spark writes the reply text from the structured result; code checks every number and forbidden word and falls back to a template.
- Run on a laptop behind a tunnel first, then on EC2 behind CloudFront before the freeze.

## Alternatives
- Zalo first: closest to real farmers, but account approval is unverified and a block would leave no demo.
- Keep the web page and redesign it: cheapest, but does not remove the steps the farmer finds hard.
- Chat only with no web: needs a chart renderer, a command parser and removal of tested code in two days.
- A smarter "shrimp on top" rule instead of choosing: tip shape is ambiguous and there is no hand-measured truth to tune it.

## Consequences
- The existing analyse-then-save service routes are reused by the chat; the old Photo screen code is deleted.
- In Messenger development mode judges cannot message the bot unless added as testers; the video is the main proof.
- Tests use a fake transport; one manual run with a real Page is needed before the video.
- The API key and the Meta app secret live only on the server.
