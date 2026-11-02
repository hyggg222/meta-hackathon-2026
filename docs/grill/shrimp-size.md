# Grill ledger: shrimp size check

Started 1 Nov 2026. Spec (approved, revision 2 approved 1 Nov): `docs/spec/shrimp-size.md`. Flow checklist: `docs/flow-c-checklist.md`.

## Sources
- `docs/spec/shrimp-size.md`: spec (persona, flow, scope, criteria, spike results).
- `docs/research/vannamei-length-weight.md`: length-weight source for the temporary size table.
- `docs/meta-api.md`: hackathon rules, Meta API facts, SAM call sample (kept from the old dev brief).
- Old Werewolf docs (spec, ledger, stack ADR, dev brief): removed on 1 Nov, in git history.
- `records/cus1_transcript.txt` (main checkout, local only): call with the first farmer.
- `docs/research/meta-hackathon-problem-selection/report.md` (main checkout, local only): pivot research.
- Spike code (session scratchpad, may disappear): `sam/call.py`, `sam/decode.mjs`, `len/lib.py`.

## Decisions
- **Stack (1 Nov):** Python FastAPI core serves a static web page (file input with capture, so no HTTPS needed), calls SAM, runs `decode.mjs` as a subprocess for masks, measures length in Python (spike code), rules and dashboard data in Python. Reason: one server, spike code reused, easy to test with synthetic masks. Rejected: keep the Werewolf stack's two servers (extra process for no demo gain); all TypeScript (port of the length algorithm costs day 1). Risk: two runtimes, Python 3.8.

- **Storage (1 Nov):** one SQLite file on the server (stdlib sqlite3), original photos beside it in a gitignored folder. Reason: phone and laptop share one history, easy to seed and test. Rejected: JSON file (concurrent writes, no queries by day); localStorage (one device only).
- **Demo data (1 Nov):** the photo taken live in the demo is real; the earlier history is seeded and labelled "demo data" on the dashboard and said so in the video. Reason: market shrimp cannot give real growth of one pond, and unlabelled numbers would cost trust. Rejected: several market batches over several days (each batch is a different lot, so the trend means nothing, and it costs effort); unlabelled synthetic data (misleading).
- **Old docs (1 Nov):** Werewolf spec, ledger, stack ADR and dev brief removed (git history keeps them); reusable Meta facts moved to `docs/meta-api.md`.
- **Error table (1 Nov):** 5 trays, about 50 shrimp, hand-measured with a ruler; the video states n. Charlie's choice, against my advice of 12 trays (about 120 shrimp). Risk: a small sample is easy to question; the answer is to say n and the limit. Rejected: 30 trays (3+ hours of measuring in the build window).
- **Stall threshold and harvest size (1 Nov):** default constants in one config file, editable on the setup page, labelled "assumption, not verified with a farmer". Starting values (mine, not from the farmer, to be tuned): stall when average length grew under 1 mm between samples 3 days apart; harvest size 50 per kg. Tests use these values; changing them changes no code. Rejected: wait for the first farmer (blocks the rules slice); show change only with no flag (loses the stall and cost feature).
- **Size per kg table (1 Nov):** a data file, replaceable. Until the CP table arrives, use a public length-weight table for whiteleg shrimp with its source written in the file, and show the label "temporary table, not the CP table" on screen. Rejected: weigh market shrimp to build the table (different species or frozen, not a pond); show length only (loses the size-per-kg message). Follow-up done: source found, see the size per kg source entry.
- **Schedule (1 Nov):** slice 0 (real photo to SAM to lengths on screen) and design-options on 1 Nov; rules, SQLite, input form, dashboard, demo data on 2 Nov; error table (5 trays) and fixes on 3 Nov with freeze that evening; video, README, submit on 4 Nov before 22:00. Cut order when late: Spark explanation, harvest flag, UI polish; never the error table. Rejected: freeze on 2 Nov (too little time for both features and the hand measuring); freeze on 4 Nov morning (video rushed).
- **Run and checks (defaults, two-way doors, 1 Nov):** the demo runs on the laptop, the phone opens it over the local network (a file input needs no HTTPS); checks are pytest and ruff, listed in `.agent/checks`.
- **Dashboard (1 Nov):** basic only: latest average length and size per kg, change since last sample, stall flag, cost of a stall day, one line chart, one table of samples (spec criterion 35). Reason: Charlie's choice; the second top feature stays small enough to finish on 2 Nov.
- **Spec approved (1 Nov):** by Charlie.

- **Review fixes (1 Nov, reviewer in spec mode):** stall rule is per day (0.33 mm per day, needs 5 measured shrimp in both samples); harvest flag added to the dashboard list; size table is rows with interpolation, looked up at the mean length; settings edited on the setup page are saved in SQLite over the config defaults; setup keeps only pond name, default feed price and reference size; the cost of a stall day is always shown; spike code copied into `spike/` because it only lived in a temp folder.
- **Length landmark (1 Nov, two-way door):** the app measures rostrum tip to telson tip, antennae excluded; the source paper measures postorbital edge to telson tip. The data file has a length factor, default 1.0 (unverified); hand-measure both landmarks on about 10 shrimp before the error table and set it. Rejected: assume the two are equal (a 5% longer length reads about 16% too heavy, so shrimp per kg is shown about 14% too low).
- **Size per kg source (1 Nov):** formula W = 1.3669e-5 * L^3.0077 (mm, g; unrounded constants, so the 100 mm value stays 71), fitted by the research agent from Chow and Sandifer 1991 cohort means, not printed by the authors; spread about 20% (Prajapati and Ujjania 2021 gives 11 to 20% lighter shrimp). No public CP or hatchery table found. See `docs/research/vannamei-length-weight.md`.

- **Prototype verdict (2 Nov, Charlie: "duyệt, làm theo ý tưởng của bạn"):** logic prototype of the dashboard rules (stall, harvest, cost, table lookup) clicked through on six scenarios. Settled: (a) the stall rule stays a strict "under 0.33 mm per day", so 1 mm over 3 days (0.333) is not a stall; (b) the stall flag stays a comparison of the last two samples, with N shown beside every sample, because tray means are noisy (a flat pond with a 2.5 mm swing in the mean makes the flag fire on noise and hide real stalls) and the video must not present the flag as a decision; rejected "two low samples in a row" (fewer false alarms but one sample later); (c) a mean length outside 60 to 140 mm still saves the sample, with an empty size and the notice `outside_table_range`; (d) editing the minimum shrimp count after saving makes the flag "cannot tell". The prototype stays in the scratchpad and is not committed.
- **Acceptance criteria (2 Nov):** 36 criteria approved by Charlie and written into the spec, replacing the first 11. Two proposals accepted with them: table range 60 to 140 mm and the same-day case (no stall flag, says "same day").

## Open questions
- Official hackathon rules text unread; Charlie accepts the research report's summary (community sources) as the rules. Open risk: "simple image analyzers" is on the anti-project list.
- the first farmer: CP ruler table, restock date, confirm stall threshold and harvest size; two more farmers to call.
- Which bonus to chase.
- Privacy: the farmer's name, region and loss figures are in tracked files of a public repo; quoting him needs consent. Charlie decides before the first push.
- Whether the SAM mask includes antennae and how the length method prunes them (check in slice 0).
