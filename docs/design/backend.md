# Backend shape (sketch, 1 Nov 2026)

Status: approved by Charlie on 1 Nov 2026 (both deviations at the end included). Python 3.8, FastAPI, SQLite, one Node script (ADR-0002). This is the contract for the build slices; a missing parameter or an extra case is a question, not something to absorb.

## Caller's usage
```python
# app.py: routes only
@app.post("/api/samples")
async def post_sample(photo: UploadFile, day: date = Form(...)):
    return asdict(service.add_sample(await photo.read(), day))   # TrayResult, saved when sized
@app.get("/api/dashboard")
def get_dashboard():
    return asdict(service.dashboard())                            # Dashboard
@app.post("/api/feed")      # {day, kg_per_day, price_vnd}  -> service.add_feed(...)
@app.get/put("/api/settings")                                     # service.settings() / service.save_settings(s)

# service.py: the only place that knows the order
def add_sample(self, photo, day):
    tray = analyze_tray(photo, self.settings(), self.table, self.segmenter)
    if tray.status == "ok": self.store.save_sample(day, tray)     # too_few / no_reference: nothing saved
    return tray
def dashboard(self):
    return build_dashboard(self.store.samples(), self.store.feeds(), self.settings(), self.table)
```

## Types (models.py, data only)
```python
Segmenter = Callable[[bytes, str], List[np.ndarray]]    # (photo, prompt) -> full-size bool masks
Settings(pond_name, ruler_mm=150.0, card_mm=85.6, feed_price_vnd=45000, stall_mm_per_day=0.33,
         harvest_per_kg=50.0, min_measured=5)          # the one owner of min_measured
ShrimpMeasure(index, length_px, length_mm: Optional, overlapped: bool, path: List[Tuple[float,float]])
TrayResult(status: "ok"|"no_reference"|"too_few"|"no_shrimp", reference: "ruler"|"card"|"none",
           scale_px_per_mm: Optional, shrimp: List[ShrimpMeasure], n_measured, n_left_out,
           mean_length_mm: Optional, size_per_kg: Optional, notices: List[str])   # codes, not sentences
SampleRecord(id, day, n_measured, n_left_out, mean_length_mm, demo, photo_path)   # no stored size_per_kg
FeedEntry(day, kg_per_day, price_vnd)
Dashboard(empty, latest_length_mm, latest_size_per_kg, n_latest, change_length_mm, change_size_per_kg,
          n_previous, days_between, stall: Optional[bool], at_harvest: bool, stall_day_cost_vnd: Optional[int],
          chart: List[ChartPoint], rows: List[SampleRow], notices: List[str])
```
`notices` are codes such as `temporary_table`, `rough_estimate`, `outside_table_range`, `same_day`, `not_enough_shrimp`; the page owns the wording.

## Modules
| File | Public | Hides |
|---|---|---|
| `tray.py` | `analyze_tray(photo, settings, table, segmenter) -> TrayResult` | prompts, reference choice (ruler beats card), dropping reference look-alikes, status rules, scale |
| `measure.py` | `measure(shrimp_masks, px_per_mm, rule=OverlapRule()) -> List[ShrimpMeasure]` | skeleton longest path, smoothing, tip probe, edge rule. Public because it is the spec's measurement seam; only `tray.py` calls it in production |
| `sizing.py` | `SizeTable.load(path)`, `table.per_kg(length_mm) -> Optional[float]` | rows, linear interpolation, length factor, 60 to 140 mm range, temporary flag and source note |
| `dashboard.py` | `build_dashboard(samples, feeds, settings, table) -> Dashboard` | stall rule (per day, both samples at least `min_measured`, days above 0), harvest flag, cost rule, chart marks. Pure, no database |
| `store.py` | `Store(path)`: `save_sample`, `samples`, `add_feed`, `feeds`, `load_settings`, `save_settings`, `seed_demo` | sqlite3 schema; no rules |
| `sam.py` | `make_sam_segmenter(api_key, decode_script) -> Segmenter` | HTTP upload, stream, Node decode subprocess, mask rebuild, disk cache. The only file that imports requests |
| `service.py` | `Service(segmenter, store, table)`: `add_sample`, `dashboard`, `add_feed`, `settings`, `save_settings` | the call order; settings = config defaults overridden by rows in SQLite |
| `app.py` | `create_app(service) -> FastAPI` | HTTP translation only |

## Tests (pytest, no network)
- `measure`: synthetic curved masks of known length; length within 3%; antennae added change it under 3%; end touching another mask or the edge is overlapped.
- `sizing`: fixture table `[(60,328),(100,71),(140,26)]`; interpolation; length factor; outside range gives None.
- `tray`: `FakeSegmenter({"shrimp": ..., "ruler": ..., "credit card": ...})`; ruler wins; card only; neither; 4 measured is too_few, 5 is ok; zero shrimp.
- `dashboard`: hand-built records; stall boundary at 0.33 mm per day; n below 5; same day; harvest at 50; cost 4,500,000 with the latest feed on or before the latest sample day.
- `store` with `:memory:` and a temp file (settings persist after reopen). Routes with `TestClient` and a fake. `sam.py` only in a labelled-photo script that also produces the error table.

## Rules settled by the prototype (approved 2 Nov 2026)
- Mean length outside the table range (60 to 140 mm): `status` stays `"ok"`, the sample is saved, `size_per_kg` is `None`, notice `outside_table_range` (spec criterion 18).
- Stall threshold is a strict "less than 0.33 mm per day": 1 mm over 3 days (0.333) is not a stall (criterion 23).
- The stall flag stays a single comparison of the last two samples. The dashboard always carries N for each sample; the flag is noisy (see the ledger) and is never shown without N.

## Deviations from the spec to approve
- Feed is keyed by date, so the form has three fields (date, feed kg, price) and not four; "the sample it belongs to" is the date.
- `size_per_kg` is computed when read, not stored, so a new CP table or a calibrated length factor fixes old samples too.
