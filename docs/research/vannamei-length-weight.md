# Whiteleg shrimp length-weight: a temporary table for the size check

Researched 2026-11-01. All links were read on that date. Only peer-reviewed papers are used for
numbers. Trade blogs are listed as pointers only.

## 1. Question

Is there a public, citable length-weight relationship (W = a * L^b, or a table) for farmed
whiteleg shrimp (Litopenaeus / Penaeus vannamei) that can serve as a TEMPORARY table turning a
measured body length in mm into shrimp per kg, for about 60 to 140 mm?

## 2. Answer in a few lines

- Best citable base: Chow and Sandifer 1991 (Aquaculture 92:165-178). It reports mean body
  length (mm) and mean body weight (g) for 23 sex-averaged cohorts of cultured vannamei from
  61 to 121 mm, and a condition factor of 1.18 to 1.47 (x10^-5 g/mm^3). It does NOT print an
  a and b. I fitted them from its Tables 1 and 2: W = 1.367e-5 * L^3.008 (L in mm, W in g,
  R2 = 0.99; b is about 3, so the shape is isometric). This fit is mine, not the authors'.
- Cross-check: Prajapati and Ujjania 2021 (earthen pond, India, n = 252, published a and b)
  gives weights 11 to 20 percent lower than the Chow-based fit at 100 to 140 mm. Same order of
  magnitude, so the table below is usable as a temporary table, not as a measurement.
- Two other papers with published a and b (Khademzadeh and Haghi 2017; Gautam et al. 2014)
  should NOT be used (reasons in section 4).
- No public hatchery "shrimp per kg versus length" table was found (section 6).
- Expect at least +/- 20 percent on weight at a given length from the sources alone, and more
  if the project's "length" is not the same landmark (section 7).

## 3. Claims with source and what the source says

| # | Claim | Source | Edition / date |
|---|-------|--------|----------------|
| C1 | Cultured P. vannamei, tank-reared, 4 hatchery lots, 2 sites. Body length (BL) = postorbital edge to tip of telson, mm (0.1 mm). Weight in g (0.01 g). Condition factor CO = BW / BL^3 x 10^5. Cohort means at 110 to 270 days run from BL 56 to 121 mm and BW 2.5 to 25.4 g. CO of older groups (170 to 270 days) is 1.30 to 1.47; younger groups (50 to 110 days) about 1.18 to 1.30. Sexes differ little in size. | Chow S, Sandifer PA (1991) Aquaculture 92:165-178. Full text read at http://aquaanimal.net/ChiefEditor/ChowPaper/Chow1991PvannameiGrowth.pdf (author-hosted copy). | Vol. 92, 1991 (accepted 22 June 1990) |
| C2 | Earthen pond, Khambhat, Gujarat, India, Oct 2020, n = 252, pooled length 11.365 to 15.325 cm (114 to 153 mm), weight 16.85 to 46.04 g. Fitted log10(W) = -2.270 + 3.322 log10(L), L in cm, W in g, r2 = 0.941. My check: at 13.741 cm this gives 32.4 g, the paper's mean is 32.83 g, so the "a" is a log10 intercept. Length used is "posterior margin of the orbit to the tip of endopod of uropod", not rostrum to telson. Group fits: A (n 17) b 3.536, B (n 136) b 3.462, C (n 99) b 3.239. Mean condition factor K = 1.249 (W/L^3 x 100, cm). | Prajapati SD, Ujjania NC (2021) Int. J. Fauna Biol. Stud. 8(1):67-70. https://doi.org/10.22271/23940522.2021.v8.i1b.792 , PDF https://www.faunajournal.com/archives/2021/vol8issue1/PartB/8-1-4-640.pdf | Vol. 8, issue 1, 2021 (received 1 Nov 2020) |
| C3 | Pond-cultured L. vannamei, Choebdeh, Iran, n = 634, mean 11.82 cm and 8.96 g, Y = 0.0108 X^2.6935, R2 = 0.8895. Methods call X "Carapace Length" in one place and "Total Length" in another; units of the equation are not stated; condition factor 0.56. | Khademzadeh O, Haghi M (2017) Int. J. Fish. Aquat. Stud. 5(1):298-301. http://www.fisheriesjournal.com/archives/2017/vol5issue1/PartE/4-6-37-889.pdf | Vol. 5, issue 1, 2017 |
| C4 | Imported broodstock in hatcheries, Tamil Nadu, n = 313 (157 M, 156 F), total length rostral spine to telson, 79 to 160 mm. Printed W = 0.0007 L^3.2605 (M), W = 0.0004 L^3.6546 (F), weight in g, L unit not stated. | Gautam K et al. (2014) Int. J. Sci. Invent. Today 3(4):365-376. http://ijsit.com/admin/ijsit_files/STUDY%20OF%20LENGTH%20AND%20WEIGHT%20RELATIONSHIP%20OF%20LITOPENAEUS%20VANNAMEI%20(BOONE,%201931)%20FROM%20EAST%20COAST%20OF%20INDIA_IJSIT_3.4.6.pdf | Vol. 3, issue 4, 2014 |
| C5 | Freshwater tank culture (0 ppt), three densities. Exponent b = 2.99 (isometric) at 130 shrimp/m2; positive allometry at 90/m2; negative at 180/m2. Only the abstract was readable (paywall): no a and no length definition. | Araneda M, Perez EP, Gasca-Leyva E (2008) Aquaculture 283:13-18. https://doi.org/10.1016/j.aquaculture.2008.06.030 | Vol. 283, 2008 |
| C6 | Twelve earthen ponds, Sinaloa (Gulf of California): five LWR models fitted; a two-segment model was selected most often; no consistent b by water source. Abstract only, no coefficients readable. | Ramos-Torres B et al. (2026) Crustaceana 99(5):537-551. https://doi.org/10.1163/15685403-bja10523 (abstract via researchgate.net/publication/404182002) | Published 23 Apr 2026 |

## 4. Side by side, and which one to pick

| Source | Culture / wild | n | Length range | Sex | Length measured | Equation | Notes |
|---|---|---|---|---|---|---|---|
| Chow and Sandifer 1991 (C1), my fit to cohort means | Cultured, tanks, South Carolina USA | 23 cohort means | 61 to 121 mm | M and F averaged | Postorbital edge to telson tip | W = 1.367e-5 * L^3.008 (mm, g), R2 0.99 | Covers the target range best. Isometric. Fit is mine. |
| Prajapati and Ujjania 2021 (C2) | Cultured, earthen pond, India | 252 | 114 to 153 mm | Pooled | Orbit to uropod tip | W = 10^-2.270 * L_cm^3.322 (cm, g), r2 0.941 | Real published a and b, but only the top of our range. Small range, b above 3: do not extrapolate below 110 mm. |
| Khademzadeh and Haghi 2017 (C3) | Cultured, pond, Iran | 634 | about 80 to 133 mm (weekly means from their Fig 1) | Pooled | Unclear (carapace vs total) | W = 0.0108 * L_cm^2.6935 if L is in cm | Gives 5.3 g at 100 mm, about 2.7 times lighter than C1 and 2.1 times lighter than C2. Condition factor 0.56 against 1.25 to 1.45 elsewhere. Likely a length-definition or unit problem. Reject. |
| Gautam et al. 2014 (C4) | Cultured broodstock | 313 | 79 to 160 mm | M / F split | Rostral spine to telson | W = 0.0007 L^3.2605 / 0.0004 L^3.6546 | With L in mm the printed a and b give about 2.3 kg at 100 mm; the text also quotes b = 2.654 for males, which disagrees with the equation. Broodstock are also heavier than grow-out. Reject. |
| Araneda et al. 2008 (C5) | Cultured, freshwater tanks | not read | not read | not read | not read | b = 2.99 at 130 /m2 | Supports b near 3. Full text needed for a. |

**Pick:** the Chow and Sandifer based fit (C1). It is the only open source that covers
61 to 121 mm, it states its length landmark, it weighs to 0.01 g, and b is close to 3, so a
length error maps cleanly to a weight error. C2 is the sanity check: it is the only published
a and b that is usable, and it agrees to within about 20 percent. C3 and C4 are rejected because
they are internally inconsistent, not because they are lower or higher.

## 5. Computed table (from the picked fit)

Formula: W (g) = a * L^b, with L = body length in mm (postorbital edge to telson tip, as in C1).
Constants: ln a = -11.2004, b = 3.0077 (a = 1.3669e-5). Shrimp per kg = 1000 / W.

Worked example, L = 100 mm:
ln(100) = 4.60517; b * ln L = 3.0077 * 4.60517 = 13.8510; plus ln a: 13.8510 - 11.2004 = 2.6506;
W = e^2.6506 = 14.16 g; per kg = 1000 / 14.16 = 70.6, shown as 71.

Rounding: weight to 0.01 g; count per kg to the nearest whole shrimp, computed from the unrounded weight.
The check columns use C2: W = 10^(-2.270) * (L/10)^3.322.

| L (mm) | W, picked fit (g) | Shrimp per kg, picked fit | W, Gujarat check (g) | Shrimp per kg, Gujarat check |
|---|---|---|---|---|
| 60 | 3.05 | 328 | 2.07 | 484 |
| 70 | 4.84 | 206 | 3.45 | 290 |
| 80 | 7.24 | 138 | 5.37 | 186 |
| 90 | 10.31 | 97 | 7.94 | 126 |
| 100 | 14.16 | 71 | 11.27 | 89 |
| 110 | 18.86 | 53 | 15.47 | 65 |
| 120 | 24.50 | 41 | 20.66 | 48 |
| 130 | 31.17 | 32 | 26.95 | 37 |
| 140 | 38.95 | 26 | 34.47 | 29 |

Notes on the table:
- The picked fit is extrapolated above 121 mm (the 130 and 140 rows). The Gujarat column is
  extrapolated below 114 mm (rows 60 to 110) and above 153 mm is not needed.
- Simple rule as a second check: W = 1.4e-5 * L^3 (the CO of the older C1 groups) gives 14.0 g at
  100 mm and 38.4 g at 140 mm, within 1.5 percent of the fit.
- Sensitivity to the length landmark: weight scales with L^3. If the project's length is 5 percent
  longer than BL (for example rostrum tip to telson tip), the true weight is about 14 percent lower
  than the table says and the true count about 16 percent higher. No source gives the rostrum
  offset, so this is unmeasured (section 7).
- The numbers came from the script
  /tmp/claude-1000/-home-huy-meta-hack-2026-worktrees-shrimp-killtest/72292fb0-5ba7-45e3-bf04-f9f19db4ccba/scratchpad/calc.py
  (scratch file, not committed).

## 6. Hatchery or feed-company "shrimp per kg versus length" tables

None found that is both public and primary.
- Trade grading tables give count against weight only, never length. They are commercial blogs,
  so treat them as pointers: https://www.iran-fish.com/2026/09/10/vannamei-shrimp-sizes/
  (2026-09-10), https://connexosglobal.com/en/shrimp-size-chart/ ,
  http://www.kgtgroup.com/articles/standards-usage-of-packing-and-counts-for-shrimp (undated),
  https://www.shrimplytech.com/resources/vannamei-growth-chart (weight and count by day of
  culture). Their numbers agree with 1000 / W; for example 18.5 to 22 g is quoted as 45 to 55 per kg.
- Searches for CP Prima / Charoen Pokphand, Thai Union and Vietnamese hatchery or feed pages
  returned no length-versus-count table. Vietnamese farm pages quote count and weight (for
  example 9.5 g is about 105 per kg on bccaqua.com) but no length. Not finding one is not proof
  none exists; a CP or Vietnamese extension officer may hold one that is not indexed.

## 7. Still unknown or weak

- Length landmark. Chow measures from the postorbital edge to the telson tip; Prajapati from the
  orbit to the uropod tip. A photo-based length is probably rostrum tip to telson tip, which is
  longer. The offset is not in any source read, so the cube-law sensitivity above applies. Define
  the project's measured length first, then calibrate the offset on 20 to 30 real shrimp.
- The Chow-based a and b are my regression on cohort means, not on individual animals. Scatter
  among individuals is larger: Table 2 SDs are about 10 to 25 percent of the mean at harvest size.
- Only Chow covers 60 to 110 mm, and it is tank-reared in South Carolina in 1988 to 1989, not
  Asian pond shrimp. The Indian pond data (C2) start at 114 mm and give lighter shrimp.
- Condition changes with age: Chow's CO is lower in young groups (about 1.18 to 1.30) than old
  ones (1.30 to 1.47). Small shrimp are therefore lighter than a cube-law line from older ones
  suggests, so the 60 to 80 mm rows may overstate weight (count per kg may be too low there).
- Sex: small differences at grow-out sizes (C1, C2), larger in broodstock (C4). No separate
  grow-out fits by sex in the sources.
- Frozen or thawed market shrimp: no primary source was found measuring length change on
  freezing and thawing. Glaze and drip loss change the weight a trader sells but probably not the
  length; curled or bent frozen shrimp are harder to measure in a photo. All unverified.
- Head-on only: every source weighs whole, head-on shrimp. The table is not for headless tails
  (no source read for the headless ratio).
- Species: the table is for vannamei only. Other penaeids (for example black tiger, P. monodon)
  have different shapes, and market shrimp may not be vannamei. No source read compares shapes.
- Full text of Araneda 2008 and Ramos-Torres 2026 was not accessible; they may hold better fits.
