# Shrimp size check: spec

Status: APPROVED by Charlie on 1 Nov 2026, revision 2 (size table source, length landmark, reviewer fixes) approved the same day. Changes after approval need his OK. Pivot and stack reasons: `docs/adr/0001-pivot-to-shrimp-size.md`, `docs/adr/0002-stack.md`. Replaces the Werewolf plan for the hackathon entry; the old docs were removed on 1 Nov and stay in git history.

Sources: call with the first farmer, a shrimp farmer (`records/cus1_transcript.txt`, local only, timestamps in brackets below); the pivot research report (`docs/research/meta-hackathon-problem-selection/report.md`, local); the SAM spike of 1 Nov (section "What the spike showed").

## Problem and users
A small pond farmer decides every few days whether the shrimp are still growing, to keep feeding or to harvest. The only way is a cast net: catch about 1 kg, weigh it, count by hand, get "shrimp per kg" [05:47, 07:23]. It takes about 15 minutes and two people, hurts the shrimp, and the result depends on luck: the net may catch big or small ones [05:22, 07:33]. Late in the crop growth cannot be seen by eye, and one day of feed with no growth costs 4 to 5 million VND (feed 45,000 VND/kg, 100 kg a day); ten days cost 40 to 50 million [28:06, 14:57, 15:29].

First user: the first farmer. He is not farming now (rainy season) and restocks in one to three months, so no pond photo is possible before the deadline [24:38]. The demo uses market shrimp.

## Persona
An owner-operator of an intensive or semi-intensive shrimp pond. The family runs it; he decides feed and harvest himself. He samples with a cast net every 3 to 5 days once the shrimp reach about 70 per kg [05:47, 07:33].

Evidence is one farmer (the first farmer), so n=1. Unknown: his age, his phone, the network at the pond, whether he keeps a diary, what he would pay.

Caveat: 100 kg of feed a day is a big pond. The research report says most Vietnamese shrimp area is extensive or semi-intensive, so the cost pain may not hold for small farms. The demo says so.

## User flow
1. One-time setup: pond name, default feed price, reference size (the ruler's long side in mm; a credit card is 85.6 by 54 mm). Stock date and number stocked are not used in the first version.
2. Each sample: lay about 10 shrimp flat in one layer next to the ruler, tap capture on a web page (no app install).
3. Result screen: masks on the photo, length per shrimp, "N measured, M left out", size in shrimp per kg.
4. Input form: four fields (date, feed kg per day, feed price pre-filled from setup, and the sample it belongs to).
5. Dashboard (basic, see below): latest size, change since the last sample, stall flag, cost of a stall day, one line chart, a table of samples.

Target: under 2 minutes per sample.

## Top features
1. **Measure from one photo and a ruler**, with a real error table (criterion 36).
2. **Dashboard that turns size into money**, with the rules in code.

The manual input form is an enabler, not a feature to sell. Keep it to about four fields. In Charlie's words the product has three parts: the report dashboard, a page where the farmer puts in numbers by hand, and the shrimp analysis that feeds the dashboard.

## Idea in one line
Lay about 10 shrimp flat on a tray next to a ruler, take one photo; the app measures each shrimp along its body, gives the average size in shrimp per kg, compares it with the last sample, and flags a stall. the first farmer agreed this is the useful shape: about 10 shrimp, one photo, an estimate is enough, counting many is not needed [33:56 to 35:34, 36:00 to 38:15].

## Scope
**In (Must)**
- Phone page: take or upload a photo of shrimp on a tray with a reference ruler (a credit card is the fallback).
- SAM 3.1 finds the shrimp and the reference; code turns masks into millimetres: scale from the reference, length of each shrimp along its curved body.
- Overlap rule: a shrimp whose end touches another shrimp or the image edge is listed as overlapped and left out of the average. The screen says "N measured, M left out".
- Size in shrimp per kg from a replaceable data file. Until the CP ruler table of the first farmer arrives, the file holds a temporary formula from a public paper (`docs/research/vannamei-length-weight.md`). Rules live in code.
- Sample history and trend (this sample against the last), with the note that sampling error is larger than measurement error [36:00].
- A stall flag and a harvest-size flag from fixed thresholds in code. The farmer decides; the app never tells him to harvest.
- Manual input form (about four fields: feed kg per day, feed price, date, sample) and the dashboard with the cost of a day without growth. Moved up from Should on 1 Nov, because the dashboard is the second top feature.

**Should (only after Must runs end to end)**
- Spark 1.3 explains the result in Vietnamese by calling the rules (tool calls), no rule decided by the model.

**Out:** counting the whole catch, pond biomass or survival from the photo (the farmer knows the stocked number [01:06]), disease diagnosis (only "needs lab"), underwater cameras, hardware, hands-free voice control, the spoken pond diary (not validated with a farmer; test so far: numbers right, one unit slip "ky" heard as "cay" in 3 of 3 takes of one sentence).

## Acceptance criteria
Approved by Charlie on 2 Nov 2026 (36 criteria, rewritten from the first 11). Each is at least one test.

**Capture and scale**
1. Given a photo with a ruler and up to 12 shrimp, When processed, Then the scale in px per mm is shown.
2. Given a photo with a credit card and no ruler, When processed, Then the scale comes from the card (85.6 mm side).
3. Given a photo with both a ruler and a card, When processed, Then the ruler sets the scale.
4. Given no reference is found, When processed, Then the app says so and shows no millimetres and no size.
5. Given SAM finds no shrimp, When processed, Then the app says "no shrimp found" and shows no size.
6. Given the SAM call fails or times out, When processed, Then the app shows an error and saves nothing.
7. Given a photo, When processed, Then the result appears in under 10 seconds.

**Length**
8. Given a synthetic mask of known length, When measured, Then the length is within 3% (mean within 1%) of the true length.
9. Given a synthetic curved mask, When measured, Then the length follows the body and is not the bounding box.
10. Given a synthetic mask with thin antennae added, When measured, Then the length changes by less than 3%.
11. Given a shrimp whose body end touches another shrimp, When processed, Then it is listed as overlapped and left out of the average.
12. Given a shrimp whose body end touches the image edge, When processed, Then it is listed as overlapped and left out of the average.
13. Given any photo, When processed, Then the screen shows "N measured, M left out".
14. Given fewer than 5 measured shrimp, When processed, Then the app asks for a new photo, shows no size and saves nothing.
37. Given a result screen, When the farmer taps a shrimp on the photo, Then it is added to or removed from the chosen shrimp and the count, mean length and size are recomputed by the code from exactly the chosen shrimp (added 2 Nov at the farmer's request).
38. Given nothing has been tapped, When the result shows, Then the chosen shrimp are those not overlapped (the automatic rule is only the default).
39. Given fewer than 5 chosen shrimp, When the farmer tries to save, Then nothing is saved and the screen says so (same as criterion 14).
15. Given exactly 5 measured shrimp, When processed, Then the size is shown.

**Size per kg**
16. Given a mean length of 100 mm, When looked up in the temporary table, Then the result is 71 per kg (60 mm gives 328, 140 mm gives 26).
17. Given a mean length between two table rows, When looked up, Then the result is linearly interpolated.
18. Given a mean length outside 60 to 140 mm, When processed, Then the sample is still saved, the length is shown, the size is empty and the screen says "outside table range".
19. Given the temporary table is in use, When a size is shown, Then the screen shows "temporary table, not the CP table" and that the size is a rough estimate (likely off by 20% or more).
20. Given the table file is replaced with another table, When looked up, Then the new values are used with no code change (tested with a fixture table).

**Trend and flags**
21. Given two samples, When the second is saved, Then the change in average length and size is shown, with N for each.
22. Given two samples with at least 5 measured shrimp each and growth under 0.33 mm per day, When the second is saved, Then the stall flag shows.
23. Given growth of 0.33 mm per day or more (1 mm over 3 days is 0.333 and is not a stall), When the second is saved, Then no stall flag shows.
24. Given a sample with fewer than 5 measured shrimp, When compared with the previous one, Then no stall flag shows and the screen says "not enough shrimp".
25. Given only one sample, When the dashboard opens, Then no change and no flag show.
26. Given two samples on the same day, When compared, Then no stall flag shows and the screen says "same day" (no division by zero).
27. Given size at or below 50 per kg, When shown, Then the "at harvest size" flag shows, as information and not as advice.

**Cost**
28. Given 100 kg of feed per day at 45,000 VND per kg, When calculated, Then the cost of a stall day is 4,500,000 VND, using the latest feed entry on or before the latest sample's day.
29. Given no feed entry yet, When the dashboard opens, Then it shows "enter feed kg" and not 0.
30. Given a feed value that is negative or not a number, When submitted, Then the form rejects it with a message and saves nothing.

**Settings and data**
31. Given the stall or harvest threshold is edited on the setup page, When the next sample is saved, Then the new value is used.
32. Given a threshold of zero or less, When submitted, Then the setup page rejects it.
33. Given the app is restarted, When the dashboard opens, Then all samples and settings are still there.
34. Given seeded demo samples, When shown in the table or the chart, Then each is marked "demo data".

**Dashboard**
35. Given samples over several days, When the dashboard opens, Then it shows the latest average length and size, the change since the last sample, both flags, the cost, one line chart with stall dates marked, and one table of samples (date, N measured, average length, size per kg, demo data or not). Nothing else.

**Error table**
36. Given at least 5 hand-measured trays, When the report runs, Then it gives the mean absolute length error, the shrimp wrongly left out, and n. Target: mean error at most 5%; a miss is reported as measured.

**Out of scope:** counting the whole catch, biomass or survival, disease diagnosis, hardware, voice and the spoken diary, stock date and number stocked, login and multiple ponds, Spark explanation (Should).

**Not automatable:** 7 (time: stopwatch on 5 real runs over the real network); 35 (look, by eye or screenshot); 36 (hand measuring with a ruler, then a script computes the error); the "never advice to harvest" wording of 27 (read by eye).

## Test seams
- **Measurement:** masks in, lengths and flags out. Pure code, tested with synthetic masks of known length (the spike already does this: 40 shapes, mean error 0.9%).
- **Rules:** length table and thresholds in, size and flags out. Pure code, no model client. Known values from the research table: 60 mm is 328 per kg, 100 mm is 71, 140 mm is 26.
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
- Overlap rule: strict (a body end touching another shrimp) as the default choice. Lay shrimp in a single layer so few are left out. A shrimp that lies on top and is whole is wrongly left out by this rule (the farmer pointed it out on 2 Nov), so the farmer can tap shrimp to choose which ones count (criteria 37 to 39); no geometric "on top" test, because tip shape alone is ambiguous.
- Count of shrimp in the pond is not needed in the first version.
- Size table format (1 Nov): rows of length in mm and shrimp per kg, with linear interpolation between rows. The temporary file is generated from the formula below at 5 mm steps and rounded; the CP table, when it arrives, replaces the file with no code change. Size per kg is looked up at the mean length.
- Settings (1 Nov): defaults come from the config file; edits on the setup page are saved in SQLite and override the defaults.
- Stack (1 Nov): Python FastAPI serves one static page, calls SAM, measures, applies rules, stores in SQLite; one Node script (`decode.mjs`) decodes SAM masks. See `docs/grill/shrimp-size.md`.
- Demo data: the live photo is real; earlier history is seeded and labelled "demo data" on screen and in the video.
- Size per kg: a replaceable data file. Until the CP table arrives, the formula W = 1.3669e-5 * L^3.0077 (mm, g; keep these unrounded constants) fitted from Chow and Sandifer 1991 (cultured whiteleg shrimp, 61 to 121 mm); source, fit method and the spread (a pond study gives 11 to 20% lighter shrimp, which is about 25% in count) are written in the file; labelled "temporary table" on screen. Details: `docs/research/vannamei-length-weight.md`.
- Length landmark (two-way door, 1 Nov): the app measures from the rostrum tip to the telson tip, antennae excluded. The paper measures from the postorbital edge to the telson tip, which is shorter; because weight grows with length cubed, a 5% longer length reads about 16% too heavy, so the shown shrimp per kg is about 14% too low. The data file has a length factor, default 1.0 (no correction, unverified). Before the error table, hand-measure both landmarks on about 10 shrimp and set the factor.
- Stall threshold and harvest size: default constants (0.33 mm per day, 50 per kg) in a config file, editable on the setup page, labelled "assumption, not verified with a farmer".
- Schedule: slice 0 and UI options on 1 Nov; rules, storage, form and dashboard on 2 Nov; error table and fixes on 3 Nov, freeze that evening; video, README and submit on 4 Nov. Cut order when late: Spark explanation, then harvest flag, then UI polish; never the error table.

## Slices
Planned 2 Nov 2026. No prefactoring: the code is new, and the spike in `spike/` is ported inside slice 0. Module shape: `docs/design/backend.md`. Each slice is built test first, through delegate. Criterion numbers refer to the list above.

**S0. Photo to lengths on screen (walking skeleton)**
- Delivers: the farmer opens the page on the phone, takes a photo, and sees the scale, each shrimp's length in millimetres and "N measured, M left out" (no overlap rule yet: all shrimp count). The errors for no reference, no shrimp and a failed SAM call show a message. Also sets up the checks (`.agent/checks`: pytest and ruff) and records the time per photo.
- Touches: `app.create_app`, `tray.analyze_tray`, `measure.measure`, `sam.make_sam_segmenter`, the capture page.
- Criteria: 1, 2, 3, 4, 5, 6 (the "saves nothing" half comes in S3), 8, 9, 13; 7 is timed and reported here.
- Blocked by: none. The biggest slice; split off `measure` first if it does not fit one context.

**S1. Overlap rule and the minimum count**
- Delivers: shrimp whose body end touches another shrimp or the image edge are listed as overlapped and left out of the average; antennae change the length by under 3%; fewer than 5 measured shrimp gives "take a new photo" and no size; exactly 5 gives a size.
- Touches: `measure.measure` (overlap rule), `tray.analyze_tray` (status `too_few`).
- Criteria: 10, 11, 12, 14 (shown part), 15.
- Blocked by: S0.

**S2. Size per kg from the length table**
- Delivers: the result shows shrimp per kg looked up at the mean length from a replaceable data file, with the "temporary table, not the CP table" and "rough estimate" labels; outside 60 to 140 mm it shows the length only with "outside table range".
- Touches: `sizing.SizeTable`, the data file, `tray.analyze_tray`.
- Criteria: 16, 17, 18 (display part), 19, 20.
- Blocked by: S0.

**S3. Save samples and see the trend**
- Delivers: a sized sample is saved with its date (also when outside the table range); too few shrimp, no reference, no shrimp and a failed call save nothing; after a restart the samples are still there; with two samples the page shows the change in length and size with N for each; seeded demo samples exist and are marked "demo data".
- Touches: `store.Store`, `service.Service`, `app` routes, `dashboard.build_dashboard` (change only), the demo seed.
- Criteria: 6, 14 (saves nothing), 18 (saved), 21, 25, 33 (samples), 34 (data).
- Blocked by: S1, S2.

**S4. Stall flag and harvest size flag**
- Delivers: the dashboard shows the stall flag (under 0.33 mm per day, both samples with at least 5 measured shrimp, at least one day apart), "not enough shrimp" and "same day" instead of a flag when it cannot tell, and the "at harvest size" flag at 50 per kg or less, as information.
- Touches: `dashboard.build_dashboard`.
- Criteria: 22, 23, 24, 26, 27.
- Blocked by: S3.

**S5. Feed entry and the cost of a stall day**
- Delivers: a form with date, feed kg and price saves a feed entry (rejects negative or non-numeric values); the dashboard shows the cost of a stall day (100 kg at 45,000 is 4,500,000 VND) from the latest entry on or before the latest sample's day, or "enter feed kg" when there is none.
- Touches: `store` (feed), `service.add_feed`, `dashboard.build_dashboard`, the form.
- Criteria: 28, 29, 30.
- Blocked by: S4 (same dashboard code).

**S6. Setup page and saved settings**
- Delivers: the setup page edits pond name, feed price, reference size, stall threshold, harvest size and minimum count; values of zero or less are rejected; the next sample uses the new values; settings survive a restart.
- Touches: `store` (settings), `service.settings`, `app` routes, the setup page.
- Criteria: 31, 32, 33 (settings).
- Blocked by: S4.

**S7. Dashboard page**
- Delivers: one page with the latest average length and size, the change, both flags, the cost, one line chart of average length with stall dates marked, and one table of samples (date, N measured, average length, size per kg, demo data or not). Nothing else. Run design-options for the page first. The 10-second check is repeated on the finished app.
- Touches: the dashboard page, `app` route, `dashboard.build_dashboard` (chart and rows).
- Criteria: 34 (display), 35; 7 (final timing).
- Blocked by: S4, S5, S6.

**S8. Error table report**
- Delivers: a script that runs the labelled trays through the real pipeline and prints the mean absolute length error, the shrimp wrongly left out and n. The 5 trays are measured by hand on 3 Nov (and the length factor is set from about 10 shrimp measured at both landmarks first).
- Touches: a script over `tray.analyze_tray` and a file of hand measurements.
- Criteria: 36.
- Blocked by: S1 (needs no sizing, so it can run in parallel with S2 to S7).

Every criterion 1 to 36 appears above. Order for the schedule: S0 to S3 today, S4 to S7 on 2 and 3 Nov, S8 on 3 Nov, freeze that evening.

## Risks and open questions
- **Anti-project risk:** the research flags "simple image analyzers". The stall flag, the cost, the dashboard and the error table must carry the story (ADR-0001). Spark explaining results through the rules is the cheapest agent step and is the last thing to cut.
- **Weak evidence:** persona is n=1; the error table is 5 trays; no real shrimp ground truth exists yet; the spike used drawn references on clean backgrounds.
- **Size per kg is rough:** 11 to 20% in weight between two sources (about 25% in count, more below 100 mm), plus the landmark offset, plus a 5% length error that alone is about 15% in weight, plus unknown effects of frozen or non-whiteleg market shrimp. The screen and the video say so.
- **The stall flag is noisy:** the spread of one tray's mean length (about 1 to 4 mm with 5 to 10 shrimp, estimated from the research note) is larger than 0.33 mm per day over 3 days, so the flag can flip at random. The screen shows N for each sample, and the video must not present the flag as a decision.
- **Overlap rule may leave too few:** the strict rule kept 3 of 15 shrimp on a crowded photo. A tray with fewer than 5 measured shrimp gets no size (criterion 14). Measure the left-out rate in slice 0; the minimum of 5 and the rule are the first things to relax, and tray layout in a single layer is the first fix.
- **Privacy:** the farmer's name, region and loss figures appear in this tracked file of a public repo, and quoting him needs his consent. Decide before the first push (see the questions).
- **Rules are second-hand:** taken from the pivot research report (community sources). The official rules text, the rubric weights (30/25/25/20), the bonus definitions and the open-weight prize eligibility are unconfirmed.
- **Defaults are mine:** stall threshold (under 1 mm growth over 3 days) and harvest size (50 per kg) are not from the farmer; confirm with the first farmer when he answers.
- **Open:** the first farmer's CP ruler table (photo, species, sizes); his restock date and whether anyone has shrimp to photograph; two more farmers to call; which bonus to chase (Agentic fits the Spark-calls-rules design); whether the SAM mask includes antennae and how the length method prunes them.
