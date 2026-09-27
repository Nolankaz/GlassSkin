# Day 13 validation protocol

## Purpose

Day 13 evaluates the already-calibrated, frozen `v1` simulator against recorded clinical observations. This protocol is written before any validation results are produced. Today is evaluation, not tuning. Agreement rules, comparison tiers, baselines, statistics, and exclusions are fixed here before simulated outcomes are examined.

## V1 — Validation tiers

Every comparison receives exactly one tier.

| Tier | Name | Evidence and use |
|---|---|---|
| 0 | In-sample reproduction | Day 12 calibration targets from the same trial and data used during fitting. Checks the assembled simulator and its modelling assumptions; this is not validation. |
| 1 | Held-out replicate | Independent trial data that the fitter never saw. This is the strongest evidence available today; only Tier 1 counts as validation. |
| 2 | Partial / cross-source | A different statistic from the fitted trial, or a different study with weaker or uncertain comparability. May corroborate or disagree, but supports no headline validation claim and receives no agreement verdict. |
| C | Context only | Vehicle, placebo, or control information. The model has no vehicle/placebo arm, so these observations provide context rather than evaluation. |

The tretinoin V01-121A-302 and tazarotene V01-123A-302 active inflammatory-lesion series are Tier 1 held-out replicate evidence. Their patients were independent of the 301 fit trials, but the trials used the same products, closely matched protocols, endpoints, and analysis methods. They provide replication-strength validation, not fully independent cross-population validation. The 301 active series are Tier 0.

## V2 — Like-with-like statistics

Compare a reported mean with a simulated mean and a reported median with a simulated median. For Tier 0, also compare the simulated median with Day 12's median-referenced fit target in GlassSkin points; that is a separate fit-reproduction check. The response multiplier is median-1 log-normal, so its mean exceeds its median when spread is positive. Comparing a simulated median directly with a reported mean would create a bookkeeping error rather than measure model error.

For spread comparisons, use only a clearly typed **SD of percentage change** on the matching endpoint. Baseline-count SD, endpoint-count SD, standard error, and untyped parenthetical values are not SDs of percentage change and must not be treated as such. A 301 week-12 SD used to derive sigma is in-sample information, not independent validation of spread.

## V3 — Baseline and units

Every Tier 0 and Tier 1 comparison runs from that source's own observed baseline mapped to its recorded `reference_baseline_points` using Day 12's anchor rule. The current evidence maps the tretinoin and tazarotene 301 and 302 active inflammatory-lesion baselines to 7.5 points; clindamycin's reference baseline is 5.0 points. Other metrics may be held at a fixed value because each current calibrated treatment has exactly one therapeutic effect, on `inflammatory_acne`.

Report every comparison in both GlassSkin points and source-scale percentage improvement. Use positive change magnitudes for improvement, translating a source's negative percent-change notation into a positive improvement magnitude before computing an error:

`percent_improvement = 100 * change_points / baseline_points`

Evaluating a different baseline is a separate sensitivity analysis and is not validation.

## V4 — Agreement classes

For each Tier 1 row, calculate `error = simulated - reported` in percentage points, with both terms expressed as percentage improvement. Use the active-arm analysis `n` and a typed SD of percentage change from the matching 302 endpoint:

`SE_pct = reported SD of % change / sqrt(n)`

At the same week, use the corresponding 301 and 302 reported improvement values to calculate:

`replicate_gap = abs(301_value - 302_value)`

Apply these verdicts in order:

| Condition | Verdict |
|---|---|
| `abs(error) <= 2 * SE_pct` | **consistent** |
| Otherwise, `abs(error) <= replicate_gap + 2 * SE_pct` | **within replication spread** |
| Otherwise | **disagrees** |

If no typed SD is available, write **SE unavailable** and classify against the replicate gap alone: `abs(error) <= replicate_gap` is **within replication spread**; otherwise it **disagrees**. This applies to tretinoin 302 weeks 4 and 8, whose parenthetical values are untyped. Tier 0 rows are evaluated against the effect's recorded calibration RMSE in GlassSkin points, rather than Tier 1 verdict thresholds. Report the fit residual and RMSE; do not call Tier 0 agreement validation. Tier 2 rows receive an error and comparability caveat, with no verdict.

Measure the seed-to-seed SD of each reported simulated statistic across the five fixed seeds in V6. A difference smaller than `3 * seed-to-seed SD` of that statistic is indistinguishable from Monte Carlo noise; report it as such rather than interpreting its sign.

## V5 — Freeze

The following are frozen for Day 13:

- `backend/simulation/parameters/v1/`
- `backend/notes/calibration/sources.md`
- `backend/notes/calibration/evidence/`
- `backend/notes/calibration/fit_report.md`
- `backend/notes/calibration/fits/`
- `backend/notes/fit_treatment_parameters.py`

None may be changed during Day 13, regardless of validation results. Record any discovered issue in the validation report or propose a future `v2` change; do not edit `v1` to improve these comparisons.

## V6 — Monte Carlo settings

- `n_trials = 10_000` for every comparison.
- Reporting seed: `42`, a fixed non-negative integer.
- Noise-measurement seeds: `42, 43, 44, 45, 46`, five fixed seeds including the reporting seed.
- Sensitivity comparisons use common random numbers: base and perturbed runs use the same seed.

## V7 — Excluded comparisons

These exclusions are fixed before results exist to prevent post-hoc evidence shopping.

| Candidate | Reason for exclusion |
|---|---|
| Conventional-dose doxycycline 100 mg | Different regimen from the calibrated 20 mg twice-daily treatment. |
| ABSORICA isotretinoin | Different nodular endpoint, weight-based dose, and 20-week horizon from the calibrated 20 mg nightly regimen. |
| Adapalene, azelaic acid, salicylic acid, spironolactone | No calibrated `v1` effects to evaluate. |
| Non-inflammatory and total lesion series | No matching calibrated effect; aggregate non-inflammatory lesions cannot be split into blackhead and whitehead effects. |
| Clindamycin and isotretinoin reported medians of visit counts | Median endpoint count minus median baseline count is not guaranteed to equal median change. |
| Tretinoin and tazarotene 301 week-12 SDs as independent validation of spread | Those SDs influenced sigma; any comparison using them is in-sample only. |
| Vehicle/placebo arms | The model has no vehicle/placebo arm; these are Tier C context only. |

## What agreement can and cannot support

Agreement on a held-out replicate trial supports that the model can reproduce that product's population-average trajectory in a comparable trial population. It does not establish accuracy for an individual user, a different baseline, a different formulation or dose, a different population, side effects, or horizons beyond the observed trials. The current `v1` effects model only inflammatory-acne therapeutic improvement; they contain no calibrated side-effect trajectories.

## Hand-computed reference checks

These checks use the recorded source observations, Day 12 evidence, and frozen `v1` values. They are arithmetic reference values for later implementation, not simulated validation results.

| Quantity | Calculation | Reference result |
|---|---|---:|
| Tretinoin 302 week-12 `SE_pct` | `45.44 / sqrt(413)` | `2.236` percentage points |
| Tretinoin week-12 replicate gap | `abs(-50.9 - (-53.4))` | `2.5` percentage points |
| Tazarotene 302 week-12 `SE_pct` | `33.382 / sqrt(397)` | `1.675` percentage points |
| Tazarotene week-12 replicate gap | `abs(-55.52 - (-59.50))` | `3.98` percentage points |
| Tretinoin week-12 in-sample reported mean in points | `2.980967 * exp(0.703346459^2 / 2)` | `3.8175` points; `100 * 3.8175 / 7.5 ≈ 50.90%` |
| Tretinoin deterministic median change at day 84 | `3.497076838 * (1 - exp(-84 / 47.222092717))`, exponential curve, delay 0 | `2.9066` points |

The two tretinoin point checks are distinct: the first reverses Day 12's mean-to-median conversion for the reported week-12 mean; the second evaluates the fitted deterministic median curve at day 84.

## Amendments

There are currently no amendments. Once validation results exist, everything above this section is frozen. Genuine corrections must be added here as dated amendments with a reason, and identified in the validation report, rather than silently rewriting the protocol.
