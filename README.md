# Shrimp size check

Entry for the Meta Global AI Developer Hackathon 2026, Indie Developer track (solo). Build period 27 Oct to 4 Nov 2026; all project code in this repository was written in that period.

## What it does
A small shrimp farmer decides every few days whether the shrimp are still growing. Today the only way is a cast net sample: catch about 1 kg, weigh it, count by hand. It takes about 15 minutes and two people, hurts the shrimp, and the result depends on luck.

Here the farmer lays about 10 shrimp flat next to a ruler and sends one photo to a Messenger bot. The bot answers with:
- the photo with every shrimp outlined, a line along its body, its number and its length;
- the number of shrimp measured, the average length and the size in shrimp per kg;
- a short Vietnamese text written by Muse Spark.

The farmer can reply "có" to save the sample, or type the numbers of the shrimp to count (for example `1 3 5`). A web dashboard shows the trend over samples, a hint when growth looks slow, and what a day without growth costs in feed. The app never tells the farmer to harvest or sell; the farmer decides.

## How the Meta models are used
- **SAM 3.1** finds each shrimp and the ruler (one noun phrase per request: "shrimp", "ruler", "credit card"). Code turns the masks into millimetres: the scale comes from the ruler, and each length follows the curved body (longest path of the skeleton), not the bounding box.
- **Muse Spark 1.3** writes the reply text from the structured result. Every number in its text must appear in the result, words that tell the farmer to harvest or sell are refused, and any failure falls back to a fixed Vietnamese template.
- Rules live in code, never in a language model: the length table, thresholds, the slow-growth hint and the cost of a day without growth are plain Python with tests.

## Run it
Python 3.8 and Node 22.

    python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
    (cd node && npx -y npm@11 ci)
    echo "META_API_KEY=..." > .env        # never commit .env
    .venv/bin/uvicorn --factory shrimp.main:build --host 127.0.0.1 --port 8000

Open `http://127.0.0.1:8000/` for the dashboard. To turn the Messenger bot on, add `MESSENGER_PAGE_TOKEN`, `MESSENGER_APP_SECRET`, `MESSENGER_VERIFY_TOKEN` and `MESSENGER_ALLOWED_IDS` (comma separated sender ids) to `.env`; add `SPARK_REPLIES=1` to let Muse Spark write the texts and `DASHBOARD_URL` for the link in the bot's replies. The webhook is `/webhook/messenger` and needs a public HTTPS address (`docs/deploy.md` describes EC2 behind CloudFront; a Cloudflare quick tunnel works for a test).

## Tests
    make test    # 300+ tests: measurement with synthetic masks of known length, rules, store, routes, bot
    make lint

## Where things are
- `shrimp/` the app: `measure.py` (length along the body), `tray.py` (scale, choice of shrimp), `sizing.py` and `size_table.json`, `dashboard.py` (rules), `store.py` (SQLite), `messenger.py`, `conversation.py`, `render.py` (reply photo), `reply_text.py` and `spark.py` (texts), `static/index.html` (dashboard page).
- `node/decode.mjs` decodes SAM masks with the official `@meta-sam/parser` npm package, run as a subprocess.
- `docs/spec/shrimp-size.md` spec and acceptance criteria; `docs/adr/` decisions; `docs/grill/` the decision ledger; `GLOSSARY.md` terms.
