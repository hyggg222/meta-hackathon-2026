# ADR-0001: Build the shrimp size check instead of the Werewolf game master

Date: 2026-11-01
Status: proposed

## Context
The first idea was Moderator, an AI game master for in-person Werewolf. The pivot research (31 Oct, `docs/research/meta-hackathon-problem-selection/report.md`, local) found that entertainment projects win Creative prizes but score weakly on Impact, which community sources weight at 30%. In play tests the gesture selectors were not reliable enough: pointing was right first try only about 60 to 80% of the time.

The same research scored 15 candidates. Shrimp sampling scored highest (7.75 of 10, the author's judgement). A real user exists (a family shrimp farmer, the first farmer), a 52-minute call confirmed the pain (a cast net sample takes about 15 minutes and two people, and a stalled feed day costs about 4.5M VND), and the demo works on market shrimp. A 1 Nov spike showed SAM 3.1 separating shrimp and a length-along-the-body method with 0.9% mean error on synthetic shapes.

Deadline: submit before 22:00 on 4 Nov 2026 (hard limit 01:00 on 5 Nov Ireland time). Solo.

## Decision
Build the shrimp size check: one phone photo of about 10 shrimp next to a ruler gives the length of each shrimp, the size in shrimp per kg, the trend over samples, a stall flag and the cost of a day without growth. Rules live in code. Spec: `docs/spec/shrimp-size.md`. The Werewolf docs are removed and stay in git history.

## Alternatives
- Continue Werewolf: weak Impact, and the selector accuracy was still unsolved with three days left.
- Vehicle-inspection evidence capture (scored 7.05): needs the father's 55-check list, a car and time, none confirmed.
- Zalo voice note to costed quote for the family tour company (scored 5.95): the data and user are in reach, but it scored lowest and looks generic.

## Consequences
- Biggest risk: the community anti-project list names "simple image analyzers", and the research says size from an image alone would read that way. The stall flag, the cost of a stall day, the dashboard and a real error table are what must carry the story. The voice diary was cut, so the agent part is thin (Spark explaining results by calling the rules is the cheapest answer, and it is optional).
- Evidence is weak: no real ground-truth lengths yet, the persona is one farmer with a large pond, and the error table will be 5 trays (about 50 shrimp). The video must say n plainly.
- Demo uses market shrimp and seeded history labelled as demo data.
- The rubric weights, anti-project list and bonus prizes come from community sources; the official rules text was not read.
