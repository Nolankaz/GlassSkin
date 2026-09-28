# Day 13 Validation Report

## Scope and claim

This report interprets the frozen `v1` simulator's inflammatory-acne therapeutic effects for six calibrated treatments. Comparisons use the source-mapped baselines, active-arm outcomes, trial populations, formulations and regimens recorded in the [calibration ledger](../calibration/sources.md), and observed study visits. The [preregistered protocol](validation_protocol.md) permits a narrow claim: agreement on a held-out replicate would support reproduction of that product's population-average trajectory in a comparable trial population. It would not establish accuracy for an individual, another baseline, population, dose, formulation, metric, side effect, or horizon beyond the observed trials.

The actual held-out week-12 results **disagree** with the preregistered thresholds. The simulator is internally coherent, but `v1` has not demonstrated successful held-out week-12 replication for the available tretinoin and tazarotene endpoints. All figures below come from the [generated results](validation_results.md); the [sensitivity figure](sensitivity.png) shows the local median responses.

## Frozen evaluation setup

The evaluation used parameter version `v1`, 10,000 trials per run, reporting seed 42, and noise seeds 42–46. The raw-trial harness matched the production `simulate_many(...)` p50 path at the selected times with a maximum gap of 0.000000000000 points. The largest week-12 seed-to-seed sample SD was **0.0341 points**, for the benzoyl-peroxide median. The 302 holdout observations reside in `holdout_evidence.json`, outside the fitter's calibration evidence directory; the protocol and holdout file were recorded at checkpoint `025dbe3` before the Step 3 results. No post-results parameter tuning occurred.

These are SHA-256 fingerprints of the raw frozen parameter files, copied from the generated results:

| `simulation/parameters/v1/` file | SHA-256 |
| --- | --- |
| `benzoyl_peroxide.json` | `67ca2e040a53b174c02e2eca19eb3ec35948b10b3d3aae778a1f64d381965b98` |
| `clindamycin.json` | `9cebfcb3f83d323019a31f9effe7dcb379caf8afd98a1a0ed8196ca3062fee23` |
| `doxycycline.json` | `9c2a1d281ac4bfb9803a99be7d7d445b80dc7e7146c4ab8a4a907d27e0d1346e` |
| `isotretinoin.json` | `e354811e12663d4446d23d78b8b28b3866e39b0251f4d995582b7eca96c4172a` |
| `tazarotene.json` | `72ed7cd3d91e9af809584bd09e5b6255f80a41349c8dc0f8163abfebc5ba5096` |
| `tretinoin.json` | `afd53a8f44e3b5e00e006080e720a28621449cad45b4190446b6bdcd65e909d3` |

The protocol compares a source mean with a simulated mean and a source median with a simulated median. For mean-basis calibration, it separately checks the simulated median against the Day 12 median-referenced target. A reported mean is not interchangeable with that fitted median target.

## Tier 0 — in-sample reproduction, not validation

There are **19 Tier 0 rows** from the observations used to fit `v1`. Nine simulated median residuals lie outside their treatment's recorded fit RMSE: benzoyl peroxide day 14; clindamycin days 63 and 84; doxycycline day 60; isotretinoin days 28 and 84; tazarotene day 56; and tretinoin days 28 and 56. For example, benzoyl peroxide day 14 is −0.3056 points against RMSE 0.1857, and clindamycin day 84 is −0.1288 against RMSE 0.0992. The assembled Monte Carlo simulator does not reproduce every fitted deterministic target exactly.

At week 12, tretinoin's simulated mean is 45.43% versus the 301 reported mean of 50.90% (−5.47 percentage points), while its median residual is −0.1027 points, within the 0.1169-point fit RMSE. Tazarotene's corresponding mean error is −3.80 percentage points, with a median residual of −0.0172 points within RMSE 0.0204. The distinction matters: fitted curve residuals, population aggregation, mean-to-median conversion, and floor clamping can all separate the assembled summary from a fitted target. These rows alone do not isolate one cause, and none is independent validation.

## Tier 1 — held-out replicate validation

The 302 trial participants were independent of the 301 trial inputs used by the fitter. Both products, endpoints, protocols, and analysis methods were closely matched, so this is **replication-strength** held-out evidence, not broad external validation. The four earlier 302 rows are classified “within replication spread”; both week-12 rows are **“disagrees”** under the unchanged protocol.

| Held-out 302 week 12 | Reported mean improvement | Simulated mean improvement | Signed error | Reported SE | 301–302 gap | Tier 0 error | Clamp fraction | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Tretinoin | 53.40% | 45.43% | −7.97 pp / −0.5976 points | 2.236 pp | 2.50 pp | −5.47 pp | 0.0894 | **disagrees** |
| Tazarotene | 59.50% | 51.72% | −7.78 pp / −0.5832 points | 1.675 pp | 3.98 pp | −3.80 pp | 0.1011 | **disagrees** |

The signed errors are simulated minus reported. Tretinoin misses the protocol's `replicate gap + 2 × SE` allowance of about 6.97 pp; tazarotene misses its allowance of about 7.33 pp. The 301 errors were already negative at week 12, and the held-out 302 reported improvement was higher than 301 for both treatments. These observations help explain the direction of the misses; they are not an additive error decomposition or a reason to revise a verdict after seeing results.

The week-12 seed SD of the simulated **mean** was 0.0102 points for tretinoin and 0.0090 for tazarotene, far below the roughly 0.6-point held-out errors. Clamping affected 8.94% and 10.11% of their simulated patients, respectively. Clamping is relevant to interpreting the distribution, but these data do not prove it caused the full miss.

## Tier 2 — partial and cross-source evidence

**No formal verdict applies to any Tier 2 row.** The clindamycin label's reported 51.00% mean improvement has no observed source baseline. With analyst-selected baselines, the frozen model gives 50.62% from 5.0 points (−0.38 pp; clamp fraction 0.1328) and 36.55% from 7.5 points (−14.45 pp; 0.0509). The label also concerns a different study and an unnamed formulation, so the apparent agreement at 5.0 points is baseline-dependent, weaker-comparability evidence.

Benzoyl peroxide's same-trial end-of-study quartiles are 46.20%, 72.70%, and 87.50%; simulated day-84 p25, median, and p75 are 44.11%, 71.43%, and **100.00%**. The differences are −2.09, −1.27, and +12.50 pp, with 0.3218 clamped fraction. End of study includes week 12 *or early discontinuation*, so day 84 is an approximation. The quartiles are same-trial partial evidence, not independent validation, and the 100% p75 reflects the model's floor rather than a smoothed estimate.

## Spread and response variability

All eight comparisons use explicitly typed SDs of percentage change. Every simulated SD is below its reported counterpart. At week 12, the 302 SDs are 45.44 pp reported versus 26.93 pp simulated for tretinoin (−18.51 pp), and 33.38 versus 25.83 for tazarotene (−7.55 pp). The 301 week-12 SDs helped derive sigma, so their own comparisons are in-sample, not independent spread validation; 301 intermediate tazarotene spread is Tier 2 partial evidence.

Sigma is the strongest local driver of the simulated p10–p90 width for every treatment, so this spread gap matters for the uncertainty bands. The construction uses a positive therapeutic multiplier, and floor clamping truncates high improvements. Those mechanisms can shape simulated spread, but the eight rows alone do not apportion the observed difference between them and other model or evidence limitations. Benzoyl peroxide, clindamycin, and isotretinoin **borrow pooled sigma** because no suitable treatment-specific change spread was available. Their bands depend strongly on that borrowed assumption.

## Internal model sanity

For all six `v1` treatments, the [metamorphic tests](../../tests/test_validation.py) found that stronger magnitude increases week-12 response, longer delay moves the response threshold later, and wider sigma widens the p10–p90 band while preserving the exact sampled-median relationship specified by the model. The final focused test run passed **27 tests**, and the full suite passed **565 tests**. These checks support internal mathematical and software consistency. They do **not** prove clinical accuracy.

## Local one-at-a-time sensitivity

The week-12 analysis attempted **48 standardized perturbation cells**: 42 were constructible and six failed model validation. At each treatment's calibration baseline, the median influence order was **magnitude > time scale > delay > sigma**; the p10–p90 width order was **sigma > magnitude > time scale > delay**. These rankings use the largest absolute output change across legal sides. They describe these local model outputs, not clinical importance or interactions among parameters. The seed-noise table measures location, not width variability, so tiny width differences should not be over-read.

Four downward delay changes (benzoyl peroxide, doxycycline, tazarotene, tretinoin) would produce `delay_days = -7` and were not constructible. Isotretinoin's high ×1.2 magnitude and high ×1.2 sigma cells would make `uncertainty = 5.4353`, above the model maximum of 5.0000. Those rankings are one-sided where a cell is illegal; no smaller substitute factor was used. Magnitude's median elasticity was essentially 1 on legal, unclamped medians. Direct sigma perturbation moved week-12 medians by only about 0.17%–0.25% on constructible sides, while affecting band width materially. For tretinoin, time scale ×0.8 moved the median +7.29%; ×1.2 moved it −7.01%.

### Sigma calibration caveat

The one-at-a-time sigma perturbation holds the **already fitted** `mean_magnitude` fixed and measures direct simulation sensitivity. For mean-basis Day 12 targets, sigma also entered `median_target = reported_mean / exp(sigma² / 2)`, so it indirectly influenced the fitted magnitude. This indirect calibration path is absent from the OAT ranking; the ranking understates sigma's total calibration influence on the median. As an analytic example, tretinoin sigma 0.703346459 gives a conversion factor of **1.2806**; scaling sigma by 1.2 gives **1.4279**, an **11.50%** increase in that factor. No fitting was rerun.

## Baseline sweep

The sweep applies the **same frozen absolute-point effect** at starting severities 2.5, 5.0, 7.5, and 10.0. It is a model stress test, not clinical evidence of efficacy at those baselines. At 2.5 points, benzoyl peroxide's simulated median improvement is **100.00%** and **0.8554** of patients reach the metric floor. At its 7.5-point reference baseline, the median is 71.43% with 0.3218 clamped. The low-baseline result does not mean a clinical study predicts complete improvement; it shows heavy floor saturation when an absolute effect calibrated at 7.5 points is applied at 2.5. Isotretinoin, tazarotene, and tretinoin also reach 100% simulated median improvement at 2.5 points. No sweep median percentage exceeds 100%.

## Vehicle, placebo, and active-comparator context

The simulator fits **active-arm change from baseline**, not an active-minus-control contrast. The [source ledger](../calibration/sources.md) records the following matched inflammatory-lesion outcomes at each study's last common visit. Ratios are control improvement divided by active improvement; they are context, not a fraction of treatment effect or simulator targets.

| Calibrated treatment and study | Last common visit | Statistic | Active improvement | Vehicle/placebo improvement | Control / active |
| --- | --- | --- | ---: | ---: | ---: |
| Benzoyl peroxide 2.5% gel | Week 12 | Median | 73.3% | 42.9% vehicle | 0.585 |
| Doxycycline 20 mg twice daily | Month 6 | Mean | 50.1% | 30.2% placebo | 0.603 |
| Tazarotene 0.045% lotion, 301 | Week 12 | LS mean | 55.52% | 45.70% vehicle | 0.823 |
| Tretinoin 0.05% lotion, 301 | Week 12 | LS mean | 50.9% | 40.4% vehicle | 0.794 |

Clindamycin and isotretinoin's calibration studies used active comparators, not vehicle arms. The current simulator has no modeled vehicle/placebo response, natural history, background skincare, regression to the mean, or untreated trajectory. Controls therefore remain protocol Tier C context only, without like-for-like validation verdicts.

## Honest disagreements and limitations

- **Held-out Tier 1:** Week-12 tretinoin and tazarotene are −7.97 and −7.78 pp below their 302 reported means and both **disagree**. In-sample mean shortfalls already existed; replication gaps and reported SEs did not cover the held-out misses. The exact causal split remains unresolved.
- **In-sample Tier 0:** Nine of 19 median residuals lie outside recorded fit RMSE. These are assembly/reproduction misses, not held-out validation failures.
- **Spread:** All eight typed-SD comparisons are narrower in simulation. Pooled sigma for three treatments and floor truncation limit confidence in the bands; their individual contributions are not established here.
- **Baseline extrapolation:** Benzoyl peroxide at baseline 2.5 has 0.8554 floor clamping and a 100% median, exposing the absolute-effect model's low-baseline limitation.

The six calibrated effects cover only `inflammatory_acne` among the 17 skin metrics. The positive therapeutic multiplier cannot represent a worsening or a symmetric non-response distribution, and floor clamping caps improvement. Evidence is sparse beyond the two close 302 replicates, is regimen- and population-specific, and does not support extrapolation beyond the observed horizons. The [fit report](../calibration/fit_report.md) flags extrapolated asymptotes for doxycycline, isotretinoin, and tazarotene. `v1` has no calibrated side-effect effects, so it does not quantify treatment burden. Reported spread may contain biological variation, measurement error, adherence, natural fluctuation, and vehicle response. OAT sensitivity does not measure parameter interactions.

## Candidate v2 directions

Candidates for a future `v2` include proportional or hybrid baseline-dependent effects, treatment-specific spread when change-SD evidence exists, broader held-out populations and regimens, a response distribution that can represent worsening or non-response, additional calibrated effects and side effects, and curve or calibration changes justified by new evidence. These are proposals, not changes made here. **`v1` remains frozen.**

## Protocol amendments

The [protocol's amendment section](validation_protocol.md) records no amendments. No post-results protocol amendments changed the preregistered tier definitions or verdict thresholds. The generated tables preserve the original classifications, including the two week-12 disagreements.
