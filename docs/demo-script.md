# Demo video script (3 minutes)

Judging weights: Impact 30, Use of Meta AI Tooling 25, Technical Depth 20, Demo 25. Each Meta model must do something visible on screen; depth is shown with numbers.

Record on the phone (Messenger) and the laptop (dashboard). Use market shrimp laid flat next to a ruler. Nobody's face on camera; do not name the farmer. Say plainly what is demo data.

| Time | Show | Say |
| --- | --- | --- |
| 0:00 to 0:20 | A hand with a cast net sample, then the bot chat. | "A small shrimp farmer checks growth with a cast net: 15 minutes, two people, and the result depends on luck. One day of feed with no growth costs about 4.5 million dong at 100 kg a day and 45,000 a kilo (an example from the farmer's numbers)." |
| 0:20 to 1:10 | Phone: send a tray photo to the bot. The reply photo arrives, then the Vietnamese text. | "He lays about ten shrimp next to a ruler and sends one photo. SAM 3.1 finds each shrimp and the ruler; code measures each length along the curved body, with the ruler as the scale. Muse Spark writes the reply, but only from numbers the code computed." |
| 1:10 to 1:40 | Phone: type `1 3 5`, the photo is redrawn, then reply "có". | "Shrimp that touch another are left out by default. He can choose which count by typing their numbers. Nothing is saved until he says yes." |
| 1:40 to 2:15 | Laptop: dashboard (demo history labelled), the slow-growth hint, the cost of a day without growth. | "The history here is demo data. The hint says growth looks slow; it is information only, the farmer decides. The rules are plain code with tests, never the language model." |
| 2:15 to 2:45 | The error table (`docs/results/error-table.md`) and one rejected Spark text in the guard test. | "Measured against my hand measurements: mean error X% over n shrimp, market shrimp laid flat, so a lower bound. Spark's text is checked: a wrong number or 'you should harvest' is refused and a fixed template is sent." |
| 2:45 to 3:00 | Limits slide. | "Next: the hatchery's own length table, real pond photos, Zalo for farmers who use it." |

Before recording: fill X and n from the error table; seed or label demo data (the page shows the "demo data" chips); check the Messenger reply arrives in under 15 seconds.
