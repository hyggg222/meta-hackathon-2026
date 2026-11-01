# Shrimp size check: spec

Status: APPROVED by Charlie on 1 Nov 2026. Changes after this need his OK. Pivot and stack reasons: `docs/adr/0001-pivot-to-shrimp-size.md`, `docs/adr/0002-stack.md`. Replaces the Werewolf plan for the hackathon entry; the old docs were removed on 1 Nov and stay in git history.

Sources: call with the first farmer, a shrimp farmer (`records/cus1_transcript.txt`, local only, timestamps in brackets below); the pivot research report (`docs/research/meta-hackathon-problem-selection/report.md`, local); the SAM spike of 1 Nov (section "What the spike showed").

## Problem and users
A small pond farmer decides every few days whether the shrimp are still growing, to keep feeding or to harvest. The only way is a cast net: catch about 1 kg, weigh it, count by hand, get "shrimp per kg" [05:47, 07:23]. It takes about 15 minutes and two people, hurts the shrimp, and the result depends on luck: the net may catch big or small ones [05:22, 07:33]. Late in the crop growth cannot be seen by eye, and one day of feed with no growth costs 4 to 5 million VND (feed 45,000 VND/kg, 100 kg a day); ten days cost 40 to 50 million [28:06, 14:57, 15:29].

First user: the first farmer. He is not farming now (rainy season) and restocks in one to three months, so no pond photo is possible before the deadline [24:38]. The demo uses market shrimp.

## Persona
An owner-operator of an intensive or semi-intensive shrimp pond. The family runs it; he decides feed and harvest himself. He samples with a cast net every 3 to 5 days once the shrimp reach about 70 per kg [05:47, 07:33].

Evidence is one farmer (the first farmer), so n=1. Unknown: his age, his phone, the network at the pond, whether he keeps a diary, what he would pay.

Caveat: 100 kg of feed a day is a big pond. The research report says most Vietnamese shrimp area is extensive or semi-intensive, so the cost pain may not hold for small farms. The demo says so.

## User flow
1. One-time setup: pond name, stock date, number stocked, feed price, ruler type.
2. Each sample: lay about 10 shrimp flat in one layer next to the ruler, tap capture on a web page (no app install).
3. Result screen: masks on the photo, length per shrimp, "N measured, M left out", size in shrimp per kg.
4. Input form: four fields (date, feed kg per day, feed price, and the sample it belongs to).
5. Dashboard (basic, see below): latest size, change since the last sample, stall flag, cost of a stall day, one line chart, a table of samples.

Target: under 2 minutes per sample.

## Top features
1. **Measure from one photo and a ruler**, with a real error table (criterion 9).
2. **Dashboard that turns size into money**, with the rules in code.

The manual input form is an enabler, not a feature to sell. Keep it to about four fields. In Charlie's words the product has three parts: the report dashboard, a page where the farmer puts in numbers by hand, and the shrimp analysis that feeds the dashboard.

## Idea in one line
Lay about 10 shrimp flat on a tray next to a ruler, take one photo; the app measures each shrimp along its body, gives the average size in shrimp per kg, compares it with the last sample, and flags a stall. the first farmer agreed this is the useful shape: about 10 shrimp, one photo, an estimate is enough, counting many is not needed [33:56 to 35:34, 36:00 to 38:15].

## Scope
**In (Must)**
- Phone page: take or upload a photo of shrimp on a tray with a reference ruler (a credit card is the fallback).
- SAM 3.1 finds the shrimp and the reference; code turns masks into millimetres: scale from the reference, length of each shrimp along its curved body.
- Overlap rule: a shrimp whose end touches another shrimp or the image edge is listed as overlapped and left out of the average. The screen says "N measured, M left out".
- Size in shrimp per kg from a lookup table (the length table of the hatchery CP, to be copied from the ruler the first farmer gets from it). Rules live in code.
- Sample history and trend (this sample against the last), with the note that sampling error is larger than measurement error [36:00].
- A stall flag and a harvest-size flag from fixed thresholds in code. The farmer decides; the app never tells him to harvest.
- Manual input form (about four fields: feed kg per day, feed price, date, sample) and the dashboard with the cost of a day without growth. Moved up from Should on 1 Nov, because the dashboard is the second top feature.

**Should (only after Must runs end to end)**
- Spark 1.3 explains the result in Vietnamese by calling the rules (tool calls), no rule decided by the model.

**Out:** counting the whole catch, pond biomass or survival from the photo (the farmer knows the stocked number [01:06]), disease diagnosis (only "needs lab"), underwater cameras, hardware, hands-free voice control, the spoken pond diary (not validated with a farmer; test so far: numbers right, one unit slip "ky" heard as "cay" in 3 of 3 takes of one sentence).

## Acceptance criteria
1. Given a photo with a visible ruler or credit card beside up to 12 shrimp, when processed, then the scale (px per mm) is shown. Given no reference is found, then the app says so and shows no millimetres.
2. Given the masks, then each shrimp length is measured along the body, not by its bounding box, and shown in millimetres.
3. Given a shrimp whose body end touches another shrimp or the image edge, then it is listed as overlapped and not used in the average; the count of measured and left-out shrimp is shown.
4. Given fewer than 5 measured shrimp (default, to tune), then the app asks for more shrimp or a new photo instead of giving a size.
5. Given the same measurements, then the size in shrimp per kg is always the same: it comes from the table in a data file, with no model.
6. Given two samples, then the screen shows the change in average length and size between them, with the sample count for each.
7. Given the average length grew less than a set threshold between samples, then the stall flag shows. The threshold is a constant in code and is set with the first farmer.
8. Given a photo to result, then the time is under 10 seconds (SAM measured at 1.0 to 1.6 s per prompt; shrimp and reference are two prompts).
9. Given at least 5 trays (about 50 shrimp) measured by hand with a ruler, then the report gives the mean absolute length error, how many shrimp the overlap rule wrongly left out, and the sample size n. The video says n plainly; it is a small sample. Proposed target: mean absolute error at most 5% (Charlie to confirm).
10. Given feed kg per day and feed price, then the cost of a day without growth is feed kg times price, in VND (100 kg at 45,000 is 4,500,000). Pure code, no model.
11. Given samples over several days, then the dashboard shows exactly: the latest average length and size per kg, the change since the last sample, the stall flag, the cost of a stall day, one line chart of average length per sample date (stall dates marked), and a table of samples (date, N measured, average length, size per kg, demo data or not). Nothing else.

## Test seams
- **Measurement:** masks in, lengths and flags out. Pure code, tested with synthetic masks of known length (the spike already does this: 40 shapes, mean error 0.9%).
- **Rules:** length table and thresholds in, size and flags out. Pure code, no model client.
- **SAM client:** thin; checked on the labelled tray photos.

## Demo script (3 minutes)
- 0:00 to 0:20, hook: the current method and what a stalled day costs (4.5M VND). Quoting the farmer needs his consent.
- 0:20 to 1:20, one photo: masks, lengths, "N measured, M left out", size per kg (SAM 3.1).
- 1:20 to 1:50, two samples: stall flag and cost of a stall day. Spark 1.3 explains in Vietnamese by calling the rules, only if time.
- 1:50 to 2:30, the error table on 5 trays (about 50 shrimp, n stated), and honesty about sampling error.
- 2:30 to 3:00, close with a pilot ask.

## What the spike showed (1 Nov, not yet on real trays)
- SAM 3.1 with the prompt "shrimp" separated shrimp on four test photos (15, about 31, 5 and 19 masks). The last, a pile of peeled shrimp, probably over-counted by 2 to 4. Counts were checked by eye only.
- Length along the body on synthetic curved shapes of known length: mean error 0.9%, worst 3.0% (40 shapes).
- A ruler and a credit card of known size pasted into two shrimp photos at three scales and three rotations (18 images each): the ruler was found 18 of 18 times, scale error 0.41% mean, 0.61% worst; the card was found 15 of 18 times with the prompt "credit card" (the prompt "card" finds nothing), scale error 0.86% mean, 1.73% worst. The 3 misses were the card turned upright in one photo.
- Measured shrimp lengths from the card scale and from the ruler scale differed by 0.7 to 1.4%.
- Limits: the references were drawn flat on a clean background, so these errors are a lower bound. Real shrimp have no ground-truth length yet, so absolute accuracy is not known. A strict overlap rule kept only 3 of 15 shrimp in the crowded photo, so it is safe but wasteful.

## Decisions
- Reference: ruler first (the hatchery CP, where the first farmer buys shrimp, hands them out [10:05]; better in the test), credit card as fallback, prompt text "ruler" and "credit card".
- Overlap rule: strict (a body end touching another shrimp). Lay shrimp in a single layer so few are left out.
- Count of shrimp in the pond is entered by the farmer.
- Stack (1 Nov): Python FastAPI serves one static page, calls SAM, measures, applies rules, stores in SQLite; one Node script (`decode.mjs`) decodes SAM masks. See `docs/grill/shrimp-size.md`.
- Demo data: the live photo is real; earlier history is seeded and labelled "demo data" on screen and in the video.
- Size per kg: a replaceable data file. Until the CP table arrives, a public length-weight table for whiteleg shrimp (source cited in the file), labelled "temporary table" on screen.
- Stall threshold and harvest size: default constants in a config file, editable on the setup page, labelled "assumption, not verified with a farmer".
- Schedule: slice 0 and UI options on 1 Nov; rules, storage, form and dashboard on 2 Nov; error table and fixes on 3 Nov, freeze that evening; video, README and submit on 4 Nov. Cut order when late: Spark explanation, then harvest flag, then UI polish; never the error table.

## Open questions
- the first farmer's ruler table (length to shrimp per kg): photo of it, plus which species and sizes. Needed before criterion 5.
- Restock date, and whether anyone has shrimp to photograph before 4 Nov.
- Stall threshold and harvest size: defaults are in a config file; confirm them with the first farmer when he answers.
- Which bonus to chase (Agentic fits the Spark-calls-rules design).
- Two more farmers to call (not asked yet), because the persona is n=1.
- The rules are taken from the pivot research report, which relies on community sources. The official rules text, the rubric weights (30/25/25/20), the bonus definitions and the open-weight prize eligibility are unconfirmed. The research flags "simple image analyzers" as an anti-project, so the stall flag, the cost, the dashboard and the error table must carry the story (ADR-0001).
- A public source for the temporary length-weight table, to cite in its data file.
- Without the CP ruler table, the app shows length only, not shrimp per kg (criterion 5 waits for it).
