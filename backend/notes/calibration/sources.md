# Day 12 clinical evidence ledger — Step 3

This ledger records reported clinical observations and the rules proposed for later calibration. The treatment sections retain the reported values; the Step 4 addendum below records the pooled-sigma conversion, but no fitted parameters. Regimens identify the evidence, not treatment recommendations; the simulator remains informational and is not medical advice. The inputs are the local [broad extraction](research/01_broad_clinical_evidence.md), [independent audit](research/02_independent_audit.md), and [targeted longitudinal search](research/03_targeted_longitudinal_evidence.md). The audit corrects the broad extraction; the targeted search adds separate, directly sourced datasets. No clinical outcome values below were read from a graph or averaged across studies.

The targeted research file names FDA reviews, DOIs, PMIDs, and NCT records but contains no literal web URLs. Canonical DOI and ClinicalTrials.gov links below are formed from those supplied identifiers; their landing pages were not rechecked for this ledger. Journal and regulatory URLs copied from the broad extraction are identified as such. A direct FDA-review URL is **not reported in the input files**, so review number, year, table, and page remain the review locator. Do not substitute a label's endpoint for a registry's longitudinal observation simply because both concern the same product.

## Evidence and calibration policy

- **Source hierarchy:** Prefer a systematic review or guideline when it contains directly usable numbers, then a randomized controlled trial, controlled comparative study, and single-arm/open-label evidence when stronger usable data are unavailable. Several explicit numerical visits may be more useful for a curve than a higher-level final-only summary. The Day 12 plan's trusted-source set is PubMed/NCBI, NIH, FDA, ClinicalTrials.gov, AAD, and NICE; this ledger also preserves the direct journal and regulatory URLs already present in the supplied, independently audited research. Study design, formulation, arm, analysis population, and estimator remain attached to every series. No pooling or averaging of incompatible studies.
- **Reconciliation:** An explicit correction in the independent audit takes precedence over the broad extraction. Newer directly sourced longitudinal evidence takes precedence over the broad extraction for the *same* study and endpoint. Different studies, formulations, doses, populations, and estimators remain separate. Unresolved differences are recorded, not silently reconciled.
- **AI boundary:** AI can help locate, organize, interpret, and audit sources. AI-generated or recalled efficacy values never directly become simulator coefficients. Every later numerical input must trace to a cited medical source; absent data are `not reported`.
- **Later active-arm rule:** Calibrate to active-arm change from baseline, not active-minus-control. Vehicle/placebo/comparator observations are retained to show context. Neither change nor contrast is calculated here.
- **Endpoint discipline:** IL means inflammatory lesion count (usually papules/pustules), NIL means aggregate non-inflammatory lesion count (often open and closed comedones), and TL means the source's total lesion count. NIL is not separately reported blackheads and whiteheads. Nodules are not automatically all inflammatory lesions. IGA/EGSS responder success, PAHPI, quality of life, sebum, hydration, and adverse-event incidence are distinct endpoints. A side-effect incidence such as “20% experienced dryness” is not a dryness magnitude or a graded symptom trajectory. The research set has **no complete numerical graded skin-side-effect trajectory**.

### 0–10 convention to be applied later, if defensible

For a usable observed 0–4 global severity grade, the proposed convention is `points = grade * 2.5`:

| Source grade | Proposed GlassSkin points |
|---|---:|
| 0 | 0 |
| 1 | 2.5 |
| 2 | 5 |
| 3 | 7.5 |
| 4 | 10 |

For count-based evidence, the fixed *GlassSkin modeling convention* is:

| Observed count band | Inflammatory lesions | Comedonal lesions | Proposed points |
|---|---:|---:|---:|
| None | 0 | 0 | 0 |
| Mild | 1–14 | 1–19 | 5 |
| Moderate | 15–50 | 20–100 | 7.5 |
| Severe | >50 | >100 | 10 |

There is no fabricated 2.5-point count category. These count bands are a GlassSkin modeling convention, **not a universal acne grading standard**. A study's usable observed global-severity baseline may later be preferable to this coarse count mapping. Eligibility ranges are never observed baselines. Metrics without a defensible link to the reported instrument remain unmapped.

Step 4 conversion, **not performed in the treatment sections below**: for a mapped global grade, `delta_points = delta_grade * 2.5`; for lesion-count percentage change, `delta_points = fraction_change * B_ref`, where `B_ref` is the same study's observed baseline mapped under the convention above. Any other figure remains unmapped. The current engine applies an **absolute point effect** around a reference baseline while many studies report relative improvement. Applying that same absolute effect to substantially different starting severities changes the implied relative improvement; this is a model limitation, not a reason to alter the engine here.

### Variability policy for later work

If a suitable between-subject SD of **change** and a mean change are reported, the planned relations are `CV = SD / mean`, `sigma = sqrt(ln(1 + CV^2))`, `sigma = uncertainty / mean_magnitude`, and `uncertainty = sigma * mean_magnitude`. If the source reports a mean and sigma later becomes known, the median-referenced target is `reported_mean / exp(sigma^2 / 2)`. These are rules for the treatment sections; **no uncertainty, fitted magnitude, or curve parameter is calculated here**. Baseline count SD, endpoint count SD, SE, IQR, and between-arm CI must not be relabeled as SD of change. If spread is unavailable, sigma must not be set to zero; Step 4 may use a pooled sigma only with explicit provenance. Observed clinical spread can reflect biological heterogeneity, measurement error, natural fluctuation, adherence, vehicle/placebo effects, and other study variation. It is not pure biological-response variability.

### Step 4 pooled-sigma addendum

The three directly supported inflammatory-response effects contribute to the fallback. Doxycycline 20 mg BID uses month-6 absolute IL-change SE 3.87, 21 completers, and mean absolute-change magnitude 15.71: `CV = (3.87 * sqrt(21)) / 15.71 = 1.128871288`, `sigma = 0.906473644`. Tretinoin V01-121A-301 uses week-12 IL percentage-change SD 40.72 percentage points and LS mean magnitude 50.9%: `CV = 40.72 / 50.9 = 0.8`, `sigma = 0.703346459`. Tazarotene V01-123A-301 uses week-12 IL percentage-change SD 36.531 percentage points and LS mean magnitude 55.52%: `CV = 36.531 / 55.52 = 0.657979107`, `sigma = 0.599771489`. The **pooled sigma** is their arithmetic mean, **0.736530531**. The benzoyl-peroxide, clindamycin, and isotretinoin inflammatory effects borrow this pooled sigma because they lack usable between-subject response spread; borrowed values do not contribute to the mean. Benzoyl-peroxide efficacy is reported as medians and receives no mean-to-median correction. The other two borrowed effects use the pooled sigma for that correction. These conversions are recorded in the Step 4 evidence JSON; no curve fitting or treatment parameters are recorded here.

## `benzoyl_peroxide`

### Calibration status

**CORE — ready for Step 4** for the exact 2.5% gel. The week-specific efficacy is a *median* percent reduction.

### Selected regimen

2.5% aqueous benzoyl peroxide gel, nightly for 12 weeks after a two-week vehicle run-in. The separate 5% arm is not part of this dataset.

### Primary source and study design

[2017 English secondary publication](https://onlinelibrary.wiley.com/doi/full/10.1111/1346-8138.13798) of the Japanese multicenter, randomized, double-blind, vehicle-controlled phase II/III study, *Twelve-week, multicenter, placebo-controlled, randomized, double-blind, parallel-group, comparative phase II/III study of benzoyl peroxide gel in patients with acne vulgaris: A secondary publication*, *Journal of Dermatology* (original Japanese report 2014), DOI 10.1111/1346-8138.13798, PMID 28295516. Methods, Tables 1–3 and 5, and Results secondary efficacy endpoint 3. Japanese patients aged 12–49 with facial acne; entry required 11–40 IL, 20–100 NIL, and at most two nodules/cysts. The run-in excluded high vehicle responders and poor adherence. These entry ranges are not baselines.

### Sample sizes and observed baseline

609 randomized across three arms. Full analysis set (FAS): **203 active / 201 vehicle** (607 including the separate 5% arm); safety: 204/201. Visit-specific numbers for the week-specific percentages are not reported. Observed baseline *median (IQR) lesion counts*, active / vehicle: IL **18 (14–26) / 18 (14–24)**; NIL **29 (23–40) / 30 (23–43)**; TL **50 (40–63) / 51 (41–67)**. No usable observed global-severity baseline is reported.

### Longitudinal efficacy

Every row below is **median percent reduction from baseline**, FAS, Results secondary efficacy endpoint 3. Active/vehicle are matched within this trial. The FAS arm Ns are 203/201; **observed visit n and visit-specific spread are not reported** for every row. NIL is an aggregate category and TL is retained as reported rather than assigned to a separate simulator metric.

| Timepoint | Metric / instrument | Endpoint wording | Active value | Estimator | Active n | Active spread | Vehicle value | Vehicle n | Vehicle spread |
|---|---|---|---:|---|---|---|---:|---|---|
| Week 2 | IL count | Percent reduction | 36.4% | Median | FAS 203; visit n not reported | not reported | 16.4% | FAS 201; visit n not reported | not reported |
| Week 2 | NIL count | Percent reduction | 17.4% | Median | FAS 203; visit n not reported | not reported | 8.3% | FAS 201; visit n not reported | not reported |
| Week 2 | TL count | Percent reduction | 22.6% | Median | FAS 203; visit n not reported | not reported | 8.5% | FAS 201; visit n not reported | not reported |
| Week 4 | IL count | Percent reduction | 48.1% | Median | FAS 203; visit n not reported | not reported | 29.4% | FAS 201; visit n not reported | not reported |
| Week 4 | NIL count | Percent reduction | 27.2% | Median | FAS 203; visit n not reported | not reported | 13.6% | FAS 201; visit n not reported | not reported |
| Week 4 | TL count | Percent reduction | 33.8% | Median | FAS 203; visit n not reported | not reported | 14.8% | FAS 201; visit n not reported | not reported |
| Week 6 | IL count | Percent reduction | 60.4% | Median | FAS 203; visit n not reported | not reported | 27.8% | FAS 201; visit n not reported | not reported |
| Week 6 | NIL count | Percent reduction | 35.5% | Median | FAS 203; visit n not reported | not reported | 16.7% | FAS 201; visit n not reported | not reported |
| Week 6 | TL count | Percent reduction | 43.8% | Median | FAS 203; visit n not reported | not reported | 20.3% | FAS 201; visit n not reported | not reported |
| Week 12 | IL count | Percent reduction | 73.3% | Median | FAS 203; visit n not reported | not reported | 42.9% | FAS 201; visit n not reported | not reported |
| Week 12 | NIL count | Percent reduction | 57.1% | Median | FAS 203; visit n not reported | not reported | 23.1% | FAS 201; visit n not reported | not reported |
| Week 12 | TL count | Percent reduction | 62.5% | Median | FAS 203; visit n not reported | not reported | 28.8% | FAS 201; visit n not reported | not reported |

### Vehicle, variability, safety, and limits

The paper separately reports **end of study (week 12 *or early discontinuation*)** median percent reductions (IQR), active/vehicle: IL **72.7% (46.2–87.5%) / 41.7% (6.3–66.7%)**; NIL **56.5% (26.3–78.3%) / 21.9% (−13.0–53.3%)**; TL **62.2% (33.3–79.6%) / 28.6% (−3.9–54.4%)**, FAS 203/201. End-of-study median IL counts are 5 (IQR 2–11) / 11 (6–19), and absolute reductions 12 (8–18) / 7 (1–12). **These IQRs do not belong to the exact week-12 rows above.** Week 8/10 observations were graph-only in the extraction; no values were estimated. The article's abstract/body disagree on overall per-protocol total (544/554); this ledger uses FAS.

Table 5 safety incidence, active N=204 / vehicle N=201: irritation **17 (8.3%) / 2 (1.0%)**, erythema **28 (13.7%) / 4 (2.0%)**, exfoliation **39 (19.1%) / 16 (8.0%)**, and pruritus **7 (3.4%) / 0**. These are adverse-event counts, not skin-metric magnitudes. Local tolerability grade supplements were not retrieved. The source's between-arm Hodges–Lehmann estimates are distinct from the arm-specific series and were not calculated into any effect here.

### Step 4 use

Use the active-arm *median* IL series only with the matching observed baseline and clear median handling; keep vehicle as context. Aggregate NIL and TL cannot be split into blackheads/whiteheads. No side-effect magnitude or visit-specific SD is available from these rows.

## `doxycycline`

### Calibration status

**CORE — ready for Step 4** for **doxycycline hyclate 20 mg twice daily** only. This is a subantimicrobial-dose regimen, not a curve for doxycycline generally or for 100 mg/day.

### Selected regimen and primary source

Periostat doxycycline hyclate oral tablets, 20 mg morning and evening for six months. [Skidmore et al., *Effects of Subantimicrobial-Dose Doxycycline in the Treatment of Moderate Acne*](https://jamanetwork.com/journals/jamadermatology/fullarticle/479281), *Archives of Dermatology* 2003;139:459–464, DOI 10.1001/archderm.139.4.459, PMID 12707093; Methods, efficacy text, Table 2 and adverse events. Two US university clinics, randomized double-blind placebo-controlled study of adults with moderate facial acne (observed ages 18–37); other acne therapies restricted. The 10–75 papules/pustules, ≤5 nodules, and 6–200 comedones were eligibility limits, not observed means.

### Sample sizes and observed baseline

Randomized 51: active 26, placebo 25. Completed six months and supplied Table 2: **21 active / 19 placebo**. Intermediate-visit analyzed Ns are not reported; do not assign completer Ns to months 2/4. Table 2 completer baseline *mean (SE) counts*, active / placebo: IL **31.38 (4.32) / 27.37 (4.54)**; comedones **54.95 (7.69) / 51.00 (8.08)**; TL **86.33 (10.54) / 78.37 (11.08)**. The baseline facial-coverage rating and follow-up improvement rating both use 1–7 labels but are different constructs, not a usable continuous 0–4 severity baseline.

### Longitudinal efficacy

The month-2/4 figures are narrative **mean percent reductions**. A reported placebo *increase* is written as increase, not converted to a negative reduction. The month-6 Table 2 values are **mean percent changes**, printed with negative signs for improvement; the article also narrates rounded month-6 reductions of IL 50%/30%, comedones 54%/11%, and TL 52%/18%. Percent-change spread is not reported.

| Timepoint | Metric / instrument | Endpoint wording | Active value | Estimator | Active n | Active spread | Placebo value | Placebo n | Placebo spread |
|---|---|---|---|---|---|---|---|---|---|
| Month 2 | IL count | Mean reduction from baseline | 24% reduction | Mean | not reported | not reported | 9% increase | not reported | not reported |
| Month 2 | Comedone count (aggregate NIL) | Mean reduction from baseline | 25% reduction | Mean | not reported | not reported | 2% increase | not reported | not reported |
| Month 2 | TL count | Mean reduction from baseline | 25% reduction | Mean | not reported | not reported | 4% increase | not reported | not reported |
| Month 4 | IL count | Mean reduction from baseline | 36% reduction | Mean | not reported | not reported | 29% reduction | not reported | not reported |
| Month 4 | Comedone count (aggregate NIL) | Mean reduction from baseline | 32% reduction | Mean | not reported | not reported | 24% reduction | not reported | not reported |
| Month 4 | TL count | Mean reduction from baseline | 33% reduction | Mean | not reported | not reported | 26% reduction | not reported | not reported |
| Month 6 | IL count | Percent change from baseline, Table 2 | −50.1% | Mean | 21 completers | not reported | −30.2% | 19 completers | not reported |
| Month 6 | Comedone count (aggregate NIL) | Percent change from baseline, Table 2 | −53.6% | Mean | 21 completers | not reported | −10.6% | 19 completers | not reported |
| Month 6 | TL count | Percent change from baseline, Table 2 | −52.3% | Mean | 21 completers | not reported | −17.5% | 19 completers | not reported |

### Placebo, variability, safety, and limits

At month 6, Table 2 mean endpoint *counts (SE)*, active/placebo: IL **15.67 (2.75) / 19.11 (2.89)**; comedones **25.48 (4.37) / 45.58 (4.59)**; TL **41.14 (5.86) / 64.68 (6.16)**. Mean absolute changes (SE), active/placebo: IL **−15.71 (3.87) / −8.26 (4.07)**; comedones **−29.48 (7.46) / −5.42 (7.84)**; TL **−45.19 (9.93) / −13.68 (10.44)**. The SEs attach to *count and absolute-change* rows, **not** to the percent-change series. No intermediate spread is reported. Completer analysis, attrition, a small cohort, and randomized-arm sex imbalance limit generalization.

Any adverse event occurred in **12/26 (46%) active / 8/25 (32%) placebo**; rash was recorded in two active participants, with placebo rash count not reported in the extraction. No numerical graded dryness, irritation, erythema, photosensitivity, or oiliness trajectory is reported. Neither overall incidence nor rash incidence is a skin-symptom magnitude.

### Step 4 use

The active IL trajectory and completer baseline belong only to the exact 20 mg BID regimen. Preserve the distinction between narrative rounded reductions and precise Table 2 changes, and between missing intermediate spread and reported endpoint SE. Do not transfer these figures to conventional-dose doxycycline.

## `tretinoin`

### Calibration status

**CORE — ready for Step 4** for ALTRENO/IDP-121 **0.05% lotion once daily for 12 weeks**. Primary longitudinal dataset **V01-121A-301**; independent corroboration **V01-121A-302**. The two trials remain separate.

### Primary and supporting sources

The targeted extraction attributes baseline and intermediate results to **FDA NDA 209353 multidisciplinary review (2018), Tables 23, 30, 34–35, review pages 54–55, 63–64, 72–73** (direct URL not reported in the input file), and week-12 SDs to registry results. The [ALTRENO prescribing information](https://dailymed.nlm.nih.gov/dailymed/getFile.cfm?name=ALTRENO&setid=1412aba5-71aa-4cce-8db4-c189bed1852c) identifies Trial 1 as [NCT02491060](https://clinicaltrials.gov/study/NCT02491060) and Trial 2 as [NCT02535871](https://clinicaltrials.gov/study/NCT02535871), and supplies final endpoint context and pooled safety. FDA NDA 209353 identifies the corresponding internal studies as **V01-121A-301** and **V01-121A-302**, respectively. Original publication: *Novel Tretinoin 0.05% Lotion for the Once-Daily Treatment of Moderate-to-Severe Acne Vulgaris: Assessment of Efficacy and Safety in Patients Aged 9 Years and Older*, *J Drugs Dermatol* 2018;17:1084–1091, PMID 30365589. The regulatory label is a trial summary, not the primary publication.

### Study design, population, and analysis

Two randomized, double-blind, vehicle-controlled parallel phase III trials. Age ≥9, moderate/severe EGSS 3/4; facial eligibility 20–40 IL, 20–100 NIL, ≤2 nodules. These ranges are not baseline means. Study 301 locations: US/El Salvador; 302: US/Dominican Republic/Honduras. Study 301 randomized/ITT **820 (406 lotion / 414 vehicle)**; study 302 **820 (413 / 407)**. ITT means randomized and received study drug; FDA describes ANCOVA/rank ANCOVA and MCMC multiple imputation. The table Ns are **analysis-set Ns, not observed attendance at each visit**. IL is facial papules/pustules with nodules separate; NIL combines open and closed comedones.

### Observed baseline

FDA Table 30, cross-checked against each registry's baseline module: **mean (SD) lesion counts**.

| Study | Arm and analysis N | IL baseline | NIL baseline | Global severity |
|---|---|---|---|---|
| 301 | Tretinoin 406 | 26.1 (SD 5.56) | 38.0 (SD 15.67) | EGSS 0–4 categories, no continuous mean |
| 301 | Vehicle 414 | 26.4 (SD 5.63) | 39.2 (SD 16.70) | EGSS 0–4 categories, no continuous mean |
| 302 | Tretinoin 413 | 26.5 (SD 5.42) | 46.1 (SD 19.25) | EGSS 0–4 categories, no continuous mean |
| 302 | Vehicle 407 | 26.0 (SD 5.25) | 48.3 (SD 19.91) | EGSS 0–4 categories, no continuous mean |

### Longitudinal efficacy — V01-121A-301, primary

Endpoint keys: **IL% = “Percent change in inflammatory lesions”**, **NIL% = “Percent change in non-inflammatory lesions”**, from baseline at each week. Negative values are the source's signed improvement convention. Weeks 4/8 are FDA Table 35 mean-change analysis values; the displayed estimator is **not independently labeled LS mean** there. Week 12 registry explicitly labels **LS mean** and **Standard Deviation**. `U(x)` is an FDA Table 35 parenthetical with **unidentified type**, not usable SD or SE. Active/vehicle analysis Ns are 406/414; observed visit n is not reported.

| Timepoint | Metric / endpoint | Active value | Estimator | Active n | Active spread | Vehicle value | Vehicle n | Vehicle spread |
|---|---|---:|---|---|---|---:|---|---|
| Week 4 | IL% | −28.5% | FDA mean-change series | ITT 406; visit n not reported | U(37.4), untyped | −24.3% | ITT 414; visit n not reported | U(38.9), untyped |
| Week 4 | NIL% | −23.4% | FDA mean-change series | ITT 406; visit n not reported | U(35.6), untyped | −13.2% | ITT 414; visit n not reported | U(35.6), untyped |
| Week 8 | IL% | −38.8% | FDA mean-change series | ITT 406; visit n not reported | U(38.0), untyped | −32.8% | ITT 414; visit n not reported | U(39.2), untyped |
| Week 8 | NIL% | −38.3% | FDA mean-change series | ITT 406; visit n not reported | U(42.5), untyped | −19.1% | ITT 414; visit n not reported | U(44.8), untyped |
| Week 12 | IL% | −50.9% | Registry LS mean | ITT 406; visit n not reported | SD 40.72 percentage points | −40.4% | ITT 414; visit n not reported | SD 42.29 percentage points |
| Week 12 | NIL% | −47.5% | Registry LS mean | ITT 406; visit n not reported | SD 41.92 percentage points | −27.3% | ITT 414; visit n not reported | SD 43.96 percentage points |

### Longitudinal efficacy — V01-121A-302, independent corroboration

Same endpoint definitions and analysis framework; active/vehicle analysis Ns are 413/407. **No pooling with 301.**

| Timepoint | Metric / endpoint | Active value | Estimator | Active n | Active spread | Vehicle value | Vehicle n | Vehicle spread |
|---|---|---:|---|---|---|---:|---|---|
| Week 4 | IL% | −27.2% | FDA mean-change series | ITT 413; visit n not reported | U(41.9), untyped | −25.1% | ITT 407; visit n not reported | U(40.8), untyped |
| Week 4 | NIL% | −22.7% | FDA mean-change series | ITT 413; visit n not reported | U(36.4), untyped | −18.0% | ITT 407; visit n not reported | U(35.7), untyped |
| Week 8 | IL% | −42.9% | FDA mean-change series | ITT 413; visit n not reported | U(44.0), untyped | −33.8% | ITT 407; visit n not reported | U(43.6), untyped |
| Week 8 | NIL% | −32.5% | FDA mean-change series | ITT 413; visit n not reported | U(45.6), untyped | −27.4% | ITT 407; visit n not reported | U(44.7), untyped |
| Week 12 | IL% | −53.4% | Registry LS mean | ITT 413; visit n not reported | SD 45.44 percentage points | −41.5% | ITT 407; visit n not reported | SD 45.68 percentage points |
| Week 12 | NIL% | −45.6% | Registry LS mean | ITT 413; visit n not reported | SD 44.64 percentage points | −31.9% | ITT 407; visit n not reported | SD 45.79 percentage points |

### Vehicle, variability, safety, and limitations

The label separately reports week-12 **mean absolute lesion reductions**, 301 active/vehicle IL **13.1/10.2**, NIL **17.8/10.6**; 302 IL **13.9/10.7**, NIL **21.9/13.9**. These are endpoint context, not additional time-series visits. Baseline count SDs and registry-labeled week-12 *percent-change* SDs have different units and roles. FDA Table 35 intermediate parentheticals are deliberately untyped; the targeted extraction notes one FDA week-12 301 IL field printed as “407,” while registry explicitly provides SD 40.72. No guessed decimal was made. No verified week-2 numeric values, visit-specific attendance, individual data, or separate open/closed-comedone outcomes are available.

Pooled **label safety denominators** are active 767 / vehicle 783, not either efficacy trial's Ns. Application-site dryness **29 (4%) / 1 (<1%)**, pain **25 (3%) / 3 (<1%)**, erythema **12 (2%) / 1 (<1%)**, and irritation **7 (1%) / 1 (<1%)** are incidence. Any positive tolerability grade at a post-baseline visit is also occurrence, not mean severity. No numerical graded side-effect trajectory is available.

### Step 4 use

Use 301 as the primary *native IL* trajectory, with 302 only as an independent check. No transfer to tretinoin cream, gel, or a different concentration. Unlabeled intermediate parentheticals cannot supply variability, and aggregate NIL cannot produce separate blackhead/whitehead effects.

## `tazarotene`

### Calibration status

**CORE — ready for Step 4** for ARAZLO/IDP-123 **0.045% lotion once nightly for 12 weeks**. Primary dataset **V01-123A-301**; independent corroboration **V01-123A-302**. Keep them separate.

### Primary and supporting sources

The targeted extraction cites **FDA NDA 211882 multidisciplinary review (December 2019), Tables 14, 19, 22, printed pages 53, 61, 70** (direct URL not reported in the input file), plus registry [NCT03168321 (301)](https://clinicaltrials.gov/study/NCT03168321) and [NCT03168334 (302)](https://clinicaltrials.gov/study/NCT03168334). The [ARAZLO DailyMed label](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d941ff25-c221-4a55-8012-0dcf3bbcbbd1), sections 6.1 and 14, gives endpoint and pooled-safety context. Original publication: Tanghetti et al., *Tazarotene 0.045% Lotion for Once-Daily Treatment of Moderate-to-Severe Acne Vulgaris: Results from Two Phase 3 Trials*, *J Drugs Dermatol* 2020;19:70–77, DOI 10.36849/JDD.2020.3977, PMID 31985914.

### Study design, population, and analysis

Two randomized, double-blind, vehicle-controlled phase III parallel trials in the US/Canada. Age ≥9, moderate/severe EGSS 3/4; facial eligibility 20–50 IL, 25–100 NIL, ≤2 nodules. These are not observed baselines. Study 301 randomized/ITT **813 (402 lotion / 411 vehicle)**; 302 **801 (397 / 404)**. ITT means randomized and received medication; FDA describes ANCOVA/rank ANCOVA and MCMC multiple imputation. Registry endpoint Ns are analysis Ns, **not raw visit attendance**. IL is papules/pustules with nodules separate; NIL combines open and closed comedones.

### Observed baseline

FDA Table 19, *mean (SD) lesion counts*:

| Study | Arm and analysis N | IL baseline | NIL baseline | EGSS 3 / 4 counts |
|---|---|---|---|---|
| 301 | Tazarotene 402 | 28.5 (SD 7.0) | 41.1 (SD 15.7) | 368 / 34 |
| 301 | Vehicle 411 | 28.1 (SD 7.0) | 40.7 (SD 16.3) | 384 / 27 |
| 302 | Tazarotene 397 | 28.0 (SD 7.3) | 41.8 (SD 17.9) | 358 / 39 |
| 302 | Vehicle 404 | 27.9 (SD 7.1) | 40.6 (SD 16.3) | 357 / 47 |

EGSS is categorical 0–4 global severity; no continuous baseline mean is substituted.

### Longitudinal efficacy — V01-123A-301, primary

Registry endpoint wording is **“Percentage Change in Mean Lesion Counts”** at the stated week, with separate IL%/NIL% categories. Values are registry **least-squares means**; spread is explicitly labeled **Standard Deviation** of the percentage-change endpoint. A negative percentage denotes improvement. Analysis Ns are 402/411; observed visit n is not reported.

| Timepoint | Metric / endpoint | Active value | Estimator | Active n | Active spread | Vehicle value | Vehicle n | Vehicle spread |
|---|---|---:|---|---|---|---:|---|---|
| Week 4 | NIL% | −29.43% | LS mean | ITT 402; visit n not reported | SD 32.441 percentage points | −23.25% | ITT 411; visit n not reported | SD 31.817 percentage points |
| Week 4 | IL% | −27.27% | LS mean | ITT 402; visit n not reported | SD 34.980 percentage points | −29.70% | ITT 411; visit n not reported | SD 34.368 percentage points |
| Week 8 | NIL% | −43.08% | LS mean | ITT 402; visit n not reported | SD 32.430 percentage points | −34.34% | ITT 411; visit n not reported | SD 31.684 percentage points |
| Week 8 | IL% | −45.30% | LS mean | ITT 402; visit n not reported | SD 34.351 percentage points | −38.96% | ITT 411; visit n not reported | SD 34.548 percentage points |
| Week 12 | NIL% | −51.36% | LS mean | ITT 402; visit n not reported | SD 36.397 percentage points | −41.5% **FDA, see discrepancy** | ITT 411; visit n not reported | SD 35.223 **registry** |
| Week 12 | IL% | −55.52% | LS mean | ITT 402; visit n not reported | SD 36.531 percentage points | −45.70% | ITT 411; visit n not reported | SD 36.984 percentage points |

### Longitudinal efficacy — V01-123A-302, independent corroboration

Same endpoint definitions; analysis Ns 397/404. **No pooling with 301.**

| Timepoint | Metric / endpoint | Active value | Estimator | Active n | Active spread | Vehicle value | Vehicle n | Vehicle spread |
|---|---|---:|---|---|---|---:|---|---|
| Week 4 | NIL% | −35.03% | LS mean | ITT 397; visit n not reported | SD 32.776 percentage points | −24.12% | ITT 404; visit n not reported | SD 33.040 percentage points |
| Week 4 | IL% | −32.31% | LS mean | ITT 397; visit n not reported | SD 32.906 percentage points | −31.55% | ITT 404; visit n not reported | SD 32.954 percentage points |
| Week 8 | NIL% | −48.45% | LS mean | ITT 397; visit n not reported | SD 36.497 percentage points | −30.92% | ITT 404; visit n not reported | SD 36.772 percentage points |
| Week 8 | IL% | −50.38% | LS mean | ITT 397; visit n not reported | SD 32.917 percentage points | −41.66% | ITT 404; visit n not reported | SD 32.874 percentage points |
| Week 12 | NIL% | −60.00% | LS mean | ITT 397; visit n not reported | SD 34.680 percentage points | −41.58% | ITT 404; visit n not reported | SD 35.239 percentage points |
| Week 12 | IL% | −59.50% | LS mean | ITT 397; visit n not reported | SD 33.382 percentage points | −48.95% | ITT 404; visit n not reported | SD 32.898 percentage points |

### Vehicle, variability, safety, and unresolved source discrepancy

**Registry/FDA sign conflict retained:** NCT03168321 prints 301 vehicle week-12 NIL as **+41.47**, while FDA Table 22 and the original publication report a **41.5% reduction**. The 301 table above explicitly uses **FDA −41.5%** as the *vehicle value* and registry **SD 35.223** as the *spread*. This is not a corrected registry observation. FDA Table 22 also omits minus signs in 302 vehicle week-4 NIL and week-12 IL cells; the registry's **−24.12%** and **−48.95%** are used above. Do not convert the old label's treatment-difference CIs (for example 301 IL **3.3 lesions, 95% CI 1.9–4.7**) into active-arm SD. The label's separate week-12 mean absolute reductions are 301 IL **15.6 active / 12.4 vehicle**, NIL **21.0 / 16.4**, and 302 IL **16.7 / 13.4**, NIL **24.6 / 16.6**; these are contextual endpoints, not extra visits.

Pooled label safety N is **779 active / 791 vehicle**, separate from trial efficacy Ns. Application-site dryness **30 (4%) / 1 (<1%)**, pain **41 (5%) / 2 (<1%)**, and erythema **15 (2%) / 0** are incidence. Percentages for any positive grade at any post-baseline visit are occurrence, not average severity. No numerical graded side-effect trajectory is reported. Week 2 was assessed but no numeric lesion result was verified; raw attendance and individual trajectories are unavailable. Registry SDs describe percentage change, not endpoint counts or between-arm differences.

### Step 4 use

Use 301 native IL as primary and 302 independently. Retain the sign conflict, no extrapolation beyond 12 weeks, no transfer to older cream/gel formulations, and no separation of aggregate NIL into blackhead/whitehead effects.

## `clindamycin`

### Calibration status

**USABLE WITH CAVEATS — conditional Step 4 candidate** for the count trajectory of the exact study gel. The older regulatory endpoint is separate.

### Selected regimen and primary source

Clindamycin phosphate **1% gel nightly for 12 weeks**, product brand and vehicle composition **not reported**. Shah et al., [*A Prospective, Randomized, Comparative Study of Topical Minocycline Gel 4% with Topical Clindamycin Phosphate Gel 1% in Indian Patients with Acne Vulgaris*](https://doi.org/10.3390/antibiotics12091455), *Antibiotics* 2023;12:1455, DOI 10.3390/antibiotics12091455, PMID 37760751, PMC10526007; primary article Table 2. The comparator is **minocycline 4% gel nightly**, not vehicle. Two-center Indian randomized **open-label** study; eligibility age ≥9, observed clindamycin ages 14–32. Other acne medication prohibited. Do **not** call this study product Clindagel; the source does not establish that brand.

### Sample sizes and observed baseline

Randomized **100, 50 per arm**. Completed/analyzed at week 12: **45 clindamycin / 46 comparator**; the table reports visit-specific denominators. Baseline **mean (SD) lesion counts**, clindamycin/comparator: IL **4.32 (3.89) / 6.22 (5.03)**; NIL **12.74 (6.21) / 14.06 (8.22)**. TL not reported. IGA baseline 2.44 (SD 1.15) / 2.64 (0.90) exists, but the reported IGA ranges contradict the stated scale; exclude it from calibration. These baseline counts show a mild lesion burden in the selected sample.

### Longitudinal efficacy

Table 2 endpoint wording: **“Number of inflammatory lesions” (IL-C)** and **“Number of non-inflammatory lesions” (NIL-C)**. Values are *mean counts*, not percentage changes; spread is visit-specific **SD of counts**. The same visit's active minocycline comparator is retained. Baseline is stated above and is not inferred from eligibility.

| Timepoint | Metric / endpoint | Active value | Estimator | Active n | Active spread | Comparator value | Comparator n | Comparator spread |
|---|---|---:|---|---:|---|---:|---:|---|
| Week 3 | IL-C | 4.48 lesions | Mean | 50 | SD 3.59 lesions | 4.54 lesions | 50 | SD 4.36 lesions |
| Week 3 | NIL-C | 10.8 lesions | Mean | 50 | SD 4.9 lesions | 10.42 lesions | 50 | SD 6.27 lesions |
| Week 6 | IL-C | 3.36 lesions | Mean | 50 | SD 2.96 lesions | 2.8 lesions | 50 | SD 3.02 lesions |
| Week 6 | NIL-C | 9.26 lesions | Mean | 50 | SD 4.21 lesions | 7.52 lesions | 50 | SD 5.1 lesions |
| Week 9 | IL-C | 2.71 lesions | Mean | 49 | SD 2.61 lesions | 1.8 lesions | 49 | SD 2.26 lesions |
| Week 9 | NIL-C | 6.69 lesions | Mean | 49 | SD 3.7 lesions | 4.39 lesions | 49 | SD 3.7 lesions |
| Week 12 | IL-C | 1.69 lesions | Mean | 45 | SD 1.84 lesions | 0.98 lesions | 46 | SD 1.51 lesions |
| Week 12 | NIL-C | 4.49 lesions | Mean | 45 | SD 2.84 lesions | 2.07 lesions | 46 | SD 2.45 lesions |

### Comparator, variability, safety, and limitations

The source also reports active medians at weeks 3/6/9/12: IL **4/3/2/1**, NIL **10/8/6/4**; comparator IL **4/2/1/0**, NIL **10/7/4/1.5**. No median-specific spread is reported. The table SDs apply to *counts*, not to changes. Small size, open-label design, attrition, mild baseline lesion burden, unspecified brand/vehicle, and inconsistent IGA reporting reduce confidence. No numerical graded skin-side-effect trajectory is provided by the targeted extraction. The aggregate NIL count is not separate blackhead/whitehead evidence.

**Separate endpoint-only regulatory source:** [once-daily clindamycin phosphate gel 1% DailyMed label](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=ea1d4a37-7da2-4228-8451-6367e1a62554), section Clinical Studies; unnamed 12-week randomized evaluator-blinded vehicle-controlled study, trial year not reported in label. At treatment end, *mean percent lesion-count reductions* active/vehicle: IL **51%/40%**, NIL **25%/12%**, TL **38%/27%**; efficacy table N **162/82**, observed baseline and spread not reported. Safety N **168/84** is different; dry-skin incidence **0/168 / 0/84** and pruritus **1/168 / 1/84** are not severity measures. This label study is **not merged** with Shah et al.; shared concentration does not establish identical formulation, population, or estimator.

### Step 4 use

If included, use the Shah et al. active IL count trajectory only with its own observed baseline and visit Ns. Preserve the open-label/attrition caveats and keep the label as an endpoint-only comparison. No Clindagel attribution and no side-effect magnitude.

**Step 4 conversion limitation:** At week 3, the active mean IL count is 4.48 versus the observed baseline 4.32, so this visit represents worsening. A positive-magnitude `decrease` effect cannot encode that observation without reversing its direction. The Step 4 JSON retains weeks 6, 9, and 12 as targets and leaves the unconverted week-3 value in the table above; it is not replaced or interpolated.

## `isotretinoin`

### Calibration status

**USABLE WITH CAVEATS — conditional Step 4 candidate** for this exact 20 mg monotherapy regimen. It is distinct from the older ABSORICA nodular study.

### Selected regimen and primary source

Oral isotretinoin **capsules, 20 mg nightly after meals for 12 weeks**; capsule brand **not reported**. De et al., [*A prospective, randomised comparative study to evaluate safety, tolerability, and efficacy of topical minocycline gel 4% plus oral isotretinoin against oral isotretinoin only in Indian patients with moderate-to-severe acne vulgaris*](https://doi.org/10.5114/ada.2024.146870), *Advances in Dermatology and Allergology* 2025;42:164–170, DOI 10.5114/ada.2024.146870, CTRI/2023/04/052056; primary article Tables 1–2. Two-center Indian, randomized **open-label** study; comparator adds **topical minocycline 4% nightly** to the same oral regimen. Participants had moderate-to-severe acne; monotherapy ages 14–35. Other acne medication and recent antibiotics were excluded.

### Sample sizes and observed baseline

Randomized **60, 30 per arm; all completed**. Observed baseline **mean (SD) lesion counts**, oral monotherapy/comparator: IL **30.30 (8.12) / 32.90 (7.06)** using Table 2; NIL **40.67 (9.28) / 41.20 (8.96)**. TL not reported. Table 1 instead gives comparator baseline IL **32.09**, an unresolved source discrepancy; do not silently replace Table 2's 32.90. IGA baseline 3.30 (SD 0.47) / 3.43 (0.50), on a 0–4 scale, is not used in this lesion-count trajectory.

### Longitudinal efficacy

Table 2 endpoint wording: **“Number of inflammatory lesions” (IL-C)** and **“Number of non-inflammatory lesions” (NIL-C)**. Values are **mean counts**, spread is **SD of endpoint counts**, and the comparator is combination therapy rather than placebo. No change or percentage is calculated here.

| Timepoint | Metric / endpoint | Active value | Estimator | Active n | Active spread | Combination value | Combination n | Combination spread |
|---|---|---:|---|---:|---|---:|---:|---|
| Week 4 | IL-C | 22.33 lesions | Mean | 30 | SD 10.55 lesions | 23.03 lesions | 30 | SD 8.79 lesions |
| Week 4 | NIL-C | 30.9 lesions | Mean | 30 | SD 12.27 lesions | 29.23 lesions | 30 | SD 11.46 lesions |
| Week 8 | IL-C | 15.67 lesions | Mean | 30 | SD 12.45 lesions | 13.27 lesions | 30 | SD 10.8 lesions |
| Week 8 | NIL-C | 20.87 lesions | Mean | 30 | SD 15.56 lesions | 18.13 lesions | 30 | SD 13.15 lesions |
| Week 12 | IL-C | 9.87 lesions | Mean | 30 | SD 12.2 lesions | 6.03 lesions | 30 | SD 8.9 lesions |
| Week 12 | NIL-C | 14.17 lesions | Mean | 30 | SD 16.1 lesions | 9.43 lesions | 30 | SD 11.67 lesions |

### Comparator, variability, safety, and limitations

Table 2 also reports monotherapy medians at weeks 4/8/12: IL **19.5/10/2**, NIL **25.5/12/4**; comparator IL **20/8/0**, NIL **27/12/3**. Median-specific spread is not reported. The count SDs are not SDs of change. The small, open-label study and short course limit confidence; the capsule brand and precise lesion-class/anatomical boundaries are not reported. The comparator baseline IL conflict remains unresolved. No numerical graded side-effect trajectory was extracted. Neither combination outcomes nor adverse-event incidence may become a monotherapy effect.

### Step 4 use

If included, use the **20 mg after-meals monotherapy** IL count series with its own baseline. Do not transfer to ABSORICA, ABSORICA LD, weight-based dosing, another fixed dose, or nodular-only endpoints. Keep aggregate NIL distinct from blackheads/whiteheads.

## Evidence investigated but deferred from initial Day 12 calibration

The statuses below concern **readiness for this simulator's numerical curve**, not relative clinical effectiveness.

### `adapalene` — deferred / short-term evidence only

Targeted study: LYu et al., [*Efficacy and Tolerability of a Triple Acid-Containing Serum Combined With 0.1% Adapalene in Mild-to-Moderate Acne Vulgaris: A Randomized, Open-Label Controlled Trial*](https://doi.org/10.1111/jocd.70929), *J Cosmetic Dermatol* 2026, DOI 10.1111/jocd.70929, Tables 1–2. Adapalene **0.1% gel nightly for only four weeks**, then withdrawn in an eight-week study. Randomized open-label, 19 monotherapy / 22 adapalene-plus-serum comparator; analysis-set definition and visit n not reported. Monotherapy baseline *mean (SD) counts*: IL **4.26 (4.15)**, NIL **17.58 (7.18)**. On treatment: week 2 IL **3.53 (SD 3.67)**, NIL **14.95 (SD 8.66)**; week 4 IL **3.58 (SD 4.83)**, NIL **11.42 (SD 4.15)**. Comparator is combination therapy, not vehicle. IGA text/tables conflict. The week-8 observation follows adapalene withdrawal and is not an on-treatment point.

Separate 12-week anchor: Stein Gold et al., *A North American Study of Adapalene–Benzoyl Peroxide Combination Gel in the Treatment of Acne*, *Cutis* 2009;84:110–116, PMID 19746769, [NCT00422240](https://clinicaltrials.gov/study/NCT00422240). The adapalene-only 0.1% gel arm is distinct from the fixed combination; randomized/ITT arm N **420**, vehicle **418**, with LOCF. Observed baseline *median* IL **27/27**, NIL **47/46** active/vehicle; week-12 median percent reductions IL **50.0%/34.3%**, NIL **49.1%/29.5%**. Intermediate values were graphical, not extracted. These **medians** are not the same estimator as [the audited DailyMed label](https://www.dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=66858a82-cfda-4ba9-aac7-cf65499f4b1a&type=display)'s week-12 *mean* absolute (percent) changes: adapalene IL **12.3 lesions (41.7%)**, NIL **21.0 (40.8%)**; vehicle IL **8.7 (30.2%)**, NIL **11.3 (23.2%)**, table N 420/418. Label safety for the combination is not adapalene-monotherapy safety. **Do not join the four-week small study to the pivotal study's week-12 anchor to fabricate a curve.**

### `azelaic_acid` — deferred pending endpoint mapping

[2024 randomized double-blind vehicle-controlled study](https://link.springer.com/article/10.1007/s13555-024-01176-2), *Effects of 15% Azelaic Acid Gel in the Management of Post-Inflammatory Erythema and Post-Inflammatory Hyperpigmentation in Acne Vulgaris*, *Dermatology and Therapy* 14:1293–1314, DOI 10.1007/s13555-024-01176-2, PMID 38734843; 15% gel twice daily for 12 weeks. Entered 72; analyzed **30 active / 30 vehicle** after attrition. Eight missed **week-8** visits used last observation carried forward; do not imply every visit was imputed. Tables 11 and 15 give native **PAHPI median (P25–P75)** scores:

| Native PAHPI series | Baseline active / vehicle | Week 4 active / vehicle | Week 8 active / vehicle | Week 12 active / vehicle |
|---|---|---|---|---|
| PIE | 13 (12–13.25) / 12 (10–13) | 12 (9–12.25) / 12 (7.75–13) | 7 (6–11.25) / 10 (7–12) | 6 (6–8.25) / 12 (9–12) |
| PIH | 12 (9.75–12) / 12 (9.75–12) | 11 (7.75–12) / 12 (8.75–12) | 7 (6–11) / 9.5 (7.5–12) | 6 (6–7.25) / 9 (7–12) |

PAHPI is a composite with **minimum 6**, not automatically GlassSkin PIE/PIH on 0–10. Table 16 IGA uses the unresolved label **“mean (P25, P75)”**; its week-12 entries active **1 (0–2)** / vehicle **2 (1–2)** are *not used numerically*. Hydration-meter readings are not perceived dryness, sebum-meter readings are not subjective oiliness, and composite irritation incidence **20/30 (66.67%)** is not a separate graded symptom effect.

### `salicylic_acid` — not ready

[*Effectiveness of Photodynamic Therapy, 2% Salicylic Acid, and Their Combination for Moderate Acne*](https://www.dovepress.com/effectiveness-of-photodynamic-therapy-2-salicylic-acid-and-their-combi-peer-reviewed-fulltext-article-CCID), *Clinical, Cosmetic and Investigational Dermatology* 2025;18:1783–1790, DOI 10.2147/CCID.S532029, PMID 40734985. Retrospective three-group comparison, **22 analyzed per group**; selected treatment is a **2% supramolecular masque, 10 minutes daily for four weeks**, with active photodynamic comparator, not vehicle. Accessible abstract/publisher excerpts corroborate mean skin-lesion reduction rates, weeks 1–4: **8.62±3.16%, 24.19±5.88%, 39.21±9.91%, 52.35±8.75%**. Full text/tables were access-blocked in the audit; exact lesion denominator, IL/NIL split, observed baseline, visit Ns, and arm-specific harms are insufficiently verified. The listed `±` values are supported as SD by indexed methods but not independently checked against the complete table. This is not ordinary leave-on salicylic acid evidence.

### `spironolactone` — not ready for current simulator metrics

[SAFA trial](https://www.bmj.com/content/381/bmj-2022-074349), *Effectiveness of spironolactone for women with acne vulgaris in England and Wales*, *BMJ* 2023;381, DOI 10.1136/bmj-2022-074349, PMID 37192767. One pragmatic double-blind RCT, **not two independent trials**: 201 assigned spironolactone, 209 placebo; usual topical treatments permitted; 50 mg/day through week 6, then 100 mg/day if tolerated through week 24. The [NIHR 2024 report](https://pubmed.ncbi.nlm.nih.gov/39268864/) describes this same trial. **Audit-corrected week-24 Acne-QoL symptom score:** active **21.2 (SD 5.9), n=163**; placebo **17.4 (SD 5.8), n=136**. The reported **unadjusted** difference is **3.77 (95% CI 2.50–5.03)**; the **adjusted** difference is **3.45 (95% CI 2.16–4.75)**. Week-12 assessed IGA success denominators are **31/168 active** and **9/160 placebo**. The later NIHR abstract pairs those numerators with randomized denominators 201/209, which does not match its printed percentages; the audit resolves the assessed denominators to 168/160. Acne-QoL is not lesion severity; IGA success is binary responder evidence. Neither supplies the continuous lesion or compatible severity trajectory needed here.

### Conventional-dose `doxycycline` — not ready

Separate regimen: **100 mg oral capsule once daily for 16 weeks**, salt/brand not established, in Moore et al., *Efficacy and Safety of Subantimicrobial Dose, Modified-Release Doxycycline 40 mg Versus Doxycycline 100 mg Versus Placebo for the treatment of Inflammatory Lesions in Moderate and Severe Acne*, *J Drugs Dermatol* 2015;14:581–586, PMID 26091383, [NCT01320033](https://clinicaltrials.gov/study/NCT01320033). Randomized double-blind; ITT 100 mg **224**, placebo **222** (separate modified-release 40 mg arm 216). Registry week-16 LOCF *mean* facial IL change **−12.9 (SD 14.60)** active / **−12.6 (SD 16.44)** placebo, and percent change **−40.3% (SD 40.90)** / **−37.1% (SD 44.45)**; NIL change **−5.2 (SD 21.60)** / **−5.8 (SD 18.19)**. Observed **facial baseline means and qualifying intermediate facial-lesion visits were not verified**. Entry criterion 25–75 papules/pustules is not an observed baseline; serial truncal global grades are a different endpoint. **Never transfer the 20 mg twice-daily series to 100 mg/day.**

### ABSORICA isotretinoin — not selected for current metric

[ABSORICA/ABSORICA LD regulatory label](https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=3ef0cff8-19c1-4441-b780-fca6c7ee1615), Study 1, Table 3 and Figure 1; trial year not reported in label. The ABSORICA arm used **0.5 mg/kg/day in two divided doses for four weeks, then 1 mg/kg/day for 16 weeks**, under fed conditions, compared with another isotretinoin capsule. Table Ns **464/461**; observed baseline *mean nodular counts* **18.4/17.7** and week-20 *mean reduction in total nodular lesion count* **−15.68/−15.62**, active/comparator. Figure 1 has intermediate data only graphically; no values were estimated. **324 (70%)/344 (75%)** achieved ≥90% nodular reduction: responder incidence, not a mean change. Nodules on face and/or trunk are **not general inflammatory acne**. This regimen is also different from the selected 20 mg nightly study and from ABSORICA LD dosing; its evidence is historical/contextual only here.

## Evidence-status summary

`Baseline?` means an **observed** baseline on the reported instrument, never an eligibility range. `Usable spread?` names the source's spread type, not an already derived simulator uncertainty. These statuses are evidence readiness, **not an effectiveness ranking**.

| treatment_id | Exact regimen | Evidence status | Longitudinal visits | Baseline? | Usable spread? | Step 4 role |
|---|---|---|---|---|---|---|
| `benzoyl_peroxide` | 2.5% aqueous gel nightly, 12 weeks | Core | Weeks 2, 4, 6, 12 | Median count + IQR | Baseline/end-of-study IQR; no visit spread | Primary candidate; keep medians and end-of-study separate |
| `doxycycline` | Hyclate 20 mg tablets twice daily, six months | Core | Months 2, 4, 6 | Completer mean count + SE | Baseline/final SE; no interim percent spread | Exact low-dose candidate only |
| `tretinoin` | ALTRENO 0.05% lotion daily, 12 weeks | Core | Weeks 4, 8, 12 in separate 301/302 trials | Mean count + SD | Registry week-12 percent-change SD; intermediate untyped | 301 primary; 302 independent check |
| `tazarotene` | ARAZLO 0.045% lotion nightly, 12 weeks | Core | Weeks 4, 8, 12 in separate 301/302 trials | Mean count + SD | Registry visit percent-change SD | 301 primary; 302 independent check; retain sign conflict |
| `clindamycin` | Phosphate 1% gel nightly, 12 weeks; brand not reported | USABLE WITH CAVEATS | Weeks 3, 6, 9, 12 | Mean count + SD | Visit count SD, not change SD | Conditional, open-label small trial |
| `isotretinoin` | Oral capsules 20 mg nightly after meals, 12 weeks; brand not reported | USABLE WITH CAVEATS | Weeks 4, 8, 12 | Mean count + SD | Visit count SD, not change SD | Conditional, exact regimen only |
| `adapalene` | 0.1% gel nightly, stopped after week 4 | Deferred / short-term evidence only | Weeks 2, 4 on treatment | Mean count + SD | Visit count SD | No 12-week curve assembled across studies |
| `azelaic_acid` | 15% gel twice daily, 12 weeks | Deferred pending endpoint mapping | Weeks 4, 8, 12 PAHPI | PAHPI median + quartiles | Native-score quartiles | Do not map PAHPI or unresolved IGA yet |
| `salicylic_acid` | 2% supramolecular 10-minute masque daily, four weeks | Not ready | Weeks 1–4 provisional lesion rate | not reported | Abstract SD, full table unverified | Verify endpoint and baseline first |
| `spironolactone` | 50 then 100 mg/day if tolerated, with usual topicals, 24 weeks | Not ready for current metrics | QoL visits; no continuous lesion series | QoL baseline only | QoL SD; not lesion spread | No current-metric curve |
| `doxycycline` 100 mg | Oral capsule once daily, 16 weeks; brand not reported | Not ready | Week 16 facial endpoint only | Facial baseline not reported | Week-16 endpoint SD | Separate from 20 mg BID; no curve |
| ABSORICA nodular evidence | 0.5 then 1 mg/kg/day, divided doses, 20 weeks | Not selected for current metric | Week 20 numeric nodules only | Nodular mean count | not reported | Nodular-only context, no IL transfer |
