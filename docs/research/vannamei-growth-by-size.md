# Whiteleg shrimp growth rate by size, 10 g to 50 g

Researched 2026-11-02.
Question: how fast does L. vannamei grow (g/day, mm/day) from 10 to 50 g, how much does it slow with size, and what do temperature, salinity and density change?

## Answer

- Intensive ponds, warm water (29-32 C), 10 to 25 g: ADG about 0.4 to 0.7 g/day [2][3]. In length that is about 1.0 to 1.5 mm/day (derived).
- Above about 28 g one pond set slowed to 0.2 to 0.4 g/day (about 0.3 to 0.6 mm/day, derived), but disease started in the same weeks [2]. Nothing primary was found for 40 to 50 g.
- Lower figures are cycle averages, not size-specific: 0.2 g/day over 92 days in 846 Vietnam crops [4]; 0.09 to 0.19 g/day in Mexican ponds [5]; 1.5 g/week (0.21 g/day) at 16 to 26 g in US raceways [7].
- ADG falls with size in the lab: at 27 C, 0.26, 0.16, 0.09 g/day at 3.9, 10.8, 16 g [1].
- Temperature is the biggest lever: 23 C instead of 27 C cut growth by 64 percent at 10.8 g [1]. Large shrimp do best near 27 C; 30 C was 16 percent slower at 16 g [1].
- Density: 70 instead of 50 shrimp/m2 gave 36 percent lighter shrimp in the warm season [5].
- No primary source defines "normal", "slow" or "stalled". Only blogs do (stall = below 0.18 g/day [9]).

## Table

ADG from sources; length growth is derived. Derivation: W = 1.3669e-5 * L^3.0077 (mm, g; docs/research/vannamei-length-weight.md), so dL/dt = ADG * L / (3.0077 * W). Factor in mm per g: 2.96 at 10 g, 2.27 at 15 g, 1.87 at 20 g, 1.61 at 25 g, 1.42 at 30 g, 1.17 at 40 g, 1.01 at 50 g. Fit is measured up to 121 mm only (about 25 g); above that it is extrapolated, and it gives 152 mm at 50 g, not 160.

| Weight (g) | Approx. length (mm, derived) | Typical ADG, g/day (range) | Length growth, mm/day (range, derived) | Source |
|---|---|---|---|---|
| 10 | 89 | 0.5 (0.4 to 0.6) intensive pond; 0.16 in 27 C tank | 1.5 (1.2 to 1.8) | [1][2][3] |
| 15 | 102 | 0.6 (0.45 to 0.7) | 1.4 (1.0 to 1.6) | [2][3] |
| 20 | 112 | 0.5 (0.35 to 0.7) | 0.9 (0.65 to 1.3) | [2][3] |
| 25 | 121 | 0.5 (0.34 to 0.6) | 0.8 (0.55 to 1.0) | [2][3] |
| 30 | 128 | 0.35 (0.2 to 0.4), one pond set only | 0.5 (0.3 to 0.6) | [2] |
| 40 | 141 | not found (primary) | not found | |
| 50 | 152 | not found (primary) | not found | |

How the ADG numbers were made (mine, from the papers' tables): [2] from average body weight at 10-day steps, rounded to whole grams, so each value is about +/-0.1 g/day: 0.5 (10 to 15 g), 0.7 (15 to 22 g), 0.6 (22 to 28 g), 0.4 (28 to 32 g), 0.2 to 0.3 (32 to 34 g). [3] from 14-day weights: 0.43 to 0.61 (10 to 22 g), 0.34 to 0.47 (20 to 27 g); one step reads 0.94 g/day (24 to 26.5 g in 5 days), likely a data artefact, not used. Cross-check: the derived 1.2 to 1.8 mm/day at 10 g sits near the 0.8 to 1.4 mm/day measured in juveniles at 25 to 35 C [10]. Whole-cycle averages (0.09 to 0.21 g/day) are left out of the table because they include the slow early weeks.

## Factors

- Temperature [1]: at 10.8 g, growth 0.39, 1.09, 1.26 g/week at 23, 27, 30 C (23 C is 64 percent below 27 C). At 16 g: 0.31, 0.61, 0.51 g/week. Reduced growth below 23 C for all sizes; for large shrimp at 30 C or above. Optimum falls with size (above 30 C for under 5 g, about 27 C for large).
- Temperature, Vietnam [4]: average shrimp weight rises about 2 g per 1 C of water temperature four weeks earlier (846 crops, four provinces).
- Season: Mexico [5] earthen ponds, 50/m2: 0.63 g/week at 26.7 C mean (autumn-winter) vs 1.33 g/week at 31.5 C mean (spring-summer). Vietnam [3], rainy season site (Sep to Dec, 26 C, 5.8 ppt): 0.27 g/day over 90 days, vs 0.38 and 0.43 g/day over 72 and 61 days at dry-season sites (28 to 29 C, about 30 ppt). Salinity, temperature and season are mixed together there.
- Salinity: no number found for shrimp of 10 g or more. [3] links its slow rainy-season site to low salinity but cannot separate it from temperature. Juveniles at 25 to 35 C showed little growth difference between 20 and 50 ppt [11]; 3 ppt gave lower weight gain than 30 ppt in 0.75 g juveniles, no numbers read [12].
- Density [5]: warm season 50, 60, 70/m2 gave 1.33, 0.97, 0.85 g/week and final 18.6, 13.5, 11.9 g. In the cold season no difference (12.4 to 12.8 g): cold limited growth first. Tanks [6]: from 14.7 g, 1, 2, 4 kg/m2 gave 1.15, 0.62, 0.37 g/week over 21 days; the high density group caught up in the next 21 days (1.13 g/week), so a dip is not always permanent.
- Size [1]: see Answer. Tank values come from 21-day trials with feed in excess and 50/m2.

## Sources

1. Wyban J, Walsh WA, Godin DM (1995). Temperature effects on growth, feeding rate and feed conversion of the Pacific white shrimp. Aquaculture 138:267-279. https://doi.org/10.1016/0044-8486(95)00032-1 . Primary, peer-reviewed. Numbers read from the author-uploaded PDF on ResearchGate (read through a summarising scraper; figure values, not tables).
2. Ramli TH et al. (2024). Growth performance of vannamei shrimp in intensive ponds, Situbondo, East Java, Indonesia. J. Marine Resources and Coastal Management. https://doi.org/10.20473/jipk.v9i1.7624 , PDF https://jurnalsaintek.uinsa.ac.id/index.php/mrcm/article/view/2725/1117 . Primary, peer-reviewed. Three ponds, 132 to 137/m2, 23 to 33 ppt, 29 to 32 C.
3. Tran Ngoc Hai et al. (2026). Super-intensive culture of whiteleg shrimp in an integrated recirculating system (CTU-RAS), Ca Mau (Vietnamese). Can Tho Univ. J. Science Part B. https://doi.org/10.22144/ctujson.2026.130 , PDF https://ctujsvn.ctu.edu.vn/index.php/ctujsvn/article/download/8150/5209/33979 . Primary. Three sites, 600 m3 tanks, 300/m3 (not small earthen ponds).
4. Laurin E et al. (2018 per Academia metadata). Production characteristics of intensive whiteleg shrimp farming in four Vietnam provinces. Aquaculture Research. https://doi.org/10.1111/ARE.13720 , abstract read at https://www.academia.edu/127782517 . Primary. Abstract only.
5. Mena-Herrera A et al. (2006). Effects of stocking densities on growth of Pacific white shrimp in earthen ponds. Israeli J. Aquaculture-Bamidgeh 58:205-213. https://doi.org/10.46989/001c.21021 . Primary. Colima, Mexico; abstract and table values via ResearchGate.
6. Gamberoni P et al. (2026). Impact of different stocking densities on growth, welfare and physiology of L. vannamei in RAS. Sci Rep 16:9087. https://doi.org/10.1038/s41598-026-42332-2 . Primary. Germany, tanks.
7. FAO (2009). Cultured aquatic species fact sheet: Penaeus vannamei (Briggs M). https://www.fao.org/fishery/docs/CDrom/aquaculture/I1129m/file/en/en_whitelegshrimp.htm . Primary (FAO). US raceway figure of 1.5 g/week, 16 to 26 g.
8. Chow S, Sandifer PA (1991). Aquaculture 92:165-178. http://aquaanimal.net/ChiefEditor/ChowPaper/Chow1991PvannameiGrowth.pdf . Primary. Tank cohorts, South Carolina; from its tables, 14 to 22 g shrimp gained only 0.06 to 0.09 g/day between 200 and 230 days (my arithmetic, temperature not read). Not used in the table.
9. Shrimply Tech, vannamei growth chart. https://www.shrimplytech.com/resources/vannamei-growth-chart . Secondary (company blog, undated). Stall threshold and "normal" ADG quoted here are a pointer only.
10. Edwards RRC (1977). Field experiments on growth and mortality of Penaeus vannamei in a Mexican coastal lagoon complex. Estuarine Coastal Mar Sci. https://www.researchgate.net/publication/222310989 . Primary. Abstract only: juvenile total length growth 0.8 to 1.4 mm/day at 25 to 35 C; size not stated.
11. Ponce-Palafox J et al. (1997). Effects of salinity and temperature on growth and survival of juvenile P. vannamei. Aquaculture 157. https://doi.org/10.1016/S0044-8486(97)00148-8 . Primary. Abstract only (read on ScienceDirect via citing-article list); small juveniles.
12. Huang M et al. (2019). Growth and lipidomic responses of juvenile L. vannamei to low salinity. Front. Physiol. 10:1087. https://doi.org/10.3389/fphys.2019.01087 . Primary. Direction only.
Not used as evidence (snippets only): Tuoi Tre/Tepbac press on LSNV shrimp "below 0.1 g/day" (https://tuoitre.vn/khoahocphothong/giai-phap-khac-phuc-tinh-trang-tom-nuoi-cham-lon-1042376.htm , secondary, date not checked); Aquaculture Magazine 2025-05-12 on jumbo shrimp in Saudi Arabia (40 g at day 120, 60 to 70 g at day 210; secondary).

## Unknown or conflicting

- No primary source gave ADG or mm/day at 40 to 50 g in Asian ponds. Above 28 g there is one pond set [2], with disease in the same period.
- Pond ADG (0.4 to 0.7) is about 2 to 3 times the cycle averages (0.1 to 0.2) and the "optimal 1 to 1.5 g/week" that [2] quotes from another source. Sizes, density, feed and system differ, so none of these is a standard for a small Vietnamese pond.
- "Normal", "slow", "stalled": no primary threshold exists. Blog values (stall below 0.18 g/day) are not tied to size or system. A threshold for the app would have to be set from the farmer's own earlier samples.
- Length growth is derived from a length-weight fit, not measured; direct mm/day for 10 to 50 g shrimp was not found. The fit and the project's measured length landmark may differ (see the length-weight note).
- Salinity effect at harvest sizes: not found as a number. Rainy-season effect in Vietnam is confounded with temperature and salinity [3].
- Most values were read through a summarising scraper from abstracts, figures or tables; [1] and [3] values should be checked against the PDF before the demo quotes them.
