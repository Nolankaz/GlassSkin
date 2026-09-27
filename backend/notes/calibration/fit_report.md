# Day 12 Step 5 fit report

Fitted against the median-referenced Step 4 targets. RMSE and maximum error are GlassSkin points. Rows are sorted by RMSE descending. A numerical RMSE tie within 1e-8 points prefers zero delay, then `TimeCurveType` declaration order, then smaller delay. Magnitude ceiling candidates pass the bounded oracle and enter the RMSE ranking; candidates whose derived uncertainty exceeds the separate TreatmentEffect limit are ineligible for the final parameter.

Plot horizon: `min(730, max(2 × last evidence day, last evidence day + fitted time scale))`, rounded up to a whole day. Plotting does not influence fitting.

| treatment | target metric | effect kind | curve | delay days | mean magnitude | time scale days | uncertainty | RMSE | max absolute error | n points | DoF | g(t_max) | flags |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `benzoyl_peroxide` | `inflammatory_acne` | `therapeutic` | `exponential` | 0 | 5.588295 | 24.271283 | 4.115950 | 0.185693 | 0.280569 | 4 | 2 | 0.968598 | none |
| `tretinoin` | `inflammatory_acne` | `therapeutic` | `exponential` | 0 | 3.497077 | 47.222093 | 2.459657 | 0.116911 | 0.156477 | 3 | 1 | 0.831164 | none |
| `clindamycin` | `inflammatory_acne` | `therapeutic` | `delayed_linear` | 14 | 2.580818 | 81.572802 | 1.900852 | 0.099244 | 0.129533 | 3 | 1 | 0.858129 | none |
| `doxycycline` | `inflammatory_acne` | `therapeutic` | `exponential` | 0 | 3.775972 | 172.220272 | 3.422819 | 0.080923 | 0.104498 | 3 | 1 | 0.648369 | extrapolated_asymptote |
| `isotretinoin` | `inflammatory_acne` | `therapeutic` | `exponential` | 7 | 6.149709 | 79.156821 | 4.529448 | 0.063169 | 0.077284 | 3 | 1 | 0.621959 | extrapolated_asymptote |
| `tazarotene` | `inflammatory_acne` | `therapeutic` | `exponential` | 0 | 4.631018 | 59.947007 | 2.777553 | 0.020359 | 0.026805 | 3 | 1 | 0.753708 | extrapolated_asymptote |

## Candidate failures

None.

## Magnitude ceiling candidates

These candidates passed the bounded oracle and remained eligible for RMSE selection; the unconstrained magnitude optimum exceeded 10.

- `clindamycin` effect 1: exponential/delay=0; fitted=10; unconstrained_oracle=10.0299962; RMSE=0.227191491; flags=mean_magnitude_bound_hit:upper,unconstrained_magnitude_above_model_bound,extrapolated_asymptote
- `clindamycin` effect 1: exponential/delay=7; fitted=10; unconstrained_oracle=10.0259187; RMSE=0.183608106; flags=mean_magnitude_bound_hit:upper,unconstrained_magnitude_above_model_bound,extrapolated_asymptote
- `clindamycin` effect 1: exponential/delay=14; fitted=10; unconstrained_oracle=10.0190665; RMSE=0.133399317; flags=mean_magnitude_bound_hit:upper,unconstrained_magnitude_above_model_bound,extrapolated_asymptote
- `isotretinoin` effect 1: exponential/delay=0; fitted=10; unconstrained_oracle=10.0000728; RMSE=0.00685303115; flags=mean_magnitude_bound_hit:upper,unconstrained_magnitude_above_model_bound,extrapolated_asymptote

## Parameter constraint exclusions

Derived uncertainty must be <= 5 points; these fitted candidates passed the magnitude oracle but could not produce a valid TreatmentEffect.

- `clindamycin` effect 1: exponential/delay=0; derived_uncertainty=7.36530531; RMSE=0.227191491
- `clindamycin` effect 1: exponential/delay=7; derived_uncertainty=7.36530531; RMSE=0.183608106
- `clindamycin` effect 1: exponential/delay=14; derived_uncertainty=7.36530531; RMSE=0.133399317
- `isotretinoin` effect 1: exponential/delay=0; derived_uncertainty=7.36530531; RMSE=0.00685303115

## RMSE winners replaced by the uncertainty limit

- `isotretinoin` effect 1: overall RMSE winner exponential/delay=0 (0.00685303115) has derived uncertainty 7.36530531; selected exponential/delay=7 (0.0631687956)

## Evidence notes

### `benzoyl_peroxide`

CORE. Japanese randomized vehicle-controlled trial, 2.5% aqueous gel nightly for 12 weeks after a two-week vehicle run-in. Active FAS N=203; observed visit Ns and week-specific spread are not reported. Exact week-12 median reduction is distinct from the discontinuation-inclusive end-of-study median and IQR. Vehicle and aggregate NIL/TL results remain in sources.md; NIL is not split into blackheads and whiteheads. Irritation and erythema are reported as incidence, not graded magnitude, so simulated side-effect burden will be underestimated.

### `clindamycin`

USABLE WITH CAVEATS — conditional. Shah et al. 2023 randomized open-label comparison, clindamycin phosphate 1% gel nightly for 12 weeks; small study, mild baseline lesion burden, attrition to 45 active completers, unspecified brand and vehicle, active minocycline comparator rather than vehicle. Week-3 active mean IL count 4.48 exceeds observed baseline 4.32, so it is a worsening observation and cannot enter a positive-magnitude decrease effect; its raw value remains in sources.md. The fitter uses only weeks 6, 9, 12. The endpoint-only regulatory gel study is separate. No graded skin-side-effect trajectory is available, so simulated side-effect burden will be underestimated.

### `doxycycline`

CORE. Skidmore 2003 six-month placebo RCT, completer analysis (21 active, 19 placebo). One study month is represented as 30 days: months 2, 4, 6 become days 60, 120, 180. Only the active inflammatory-lesion series is fitted; placebo and aggregate comedones remain in sources.md. No graded skin-side-effect trajectory was reported, so simulated side-effect burden will be underestimated. This 20 mg BID evidence does not apply to 100 mg/day.

### `isotretinoin`

USABLE WITH CAVEATS — conditional. De et al. 2025 randomized open-label comparison, 20 mg oral capsules nightly after meals for 12 weeks, 30 monotherapy participants, all completed. Small sample, short course, unknown capsule brand; comparator adds topical minocycline and its IL baseline differs between source Tables 1 and 2. Only the monotherapy inflammatory-lesion count series is used. This is not ABSORICA, weight-based dosing, or a nodular-only endpoint. Visit count SDs are not change SDs. No graded skin-side-effect trajectory is available, so simulated side-effect burden will be underestimated.

### `tazarotene`

CORE. V01-123A-301 / NCT03168321 is the primary 12-week randomized vehicle-controlled dataset; V01-123A-302 / NCT03168334 is independent corroboration, not pooled fitter input. The registry prints +41.47 for 301 vehicle week-12 aggregate NIL while FDA Table 22 and the publication report a 41.5% reduction; this conflict does not affect the selected active IL series and is not silently repaired. Registry SDs describe percentage change, not between-arm differences. Aggregate NIL cannot be split into blackheads and whiteheads. Label dryness/irritation rates are incidence, not symptom magnitude; excluding side effects understates simulated burden. No transfer to cream or gel formulations.

### `tretinoin`

CORE. V01-121A-301 / NCT02491060 is the primary 12-week randomized vehicle-controlled dataset; V01-121A-302 / NCT02535871 is independent corroboration, not pooled fitter input. FDA week-4/8 parenthetical U(...) values are untyped and unused as spread. The week-12 registry SD is for percentage change. Aggregate non-inflammatory lesions cannot be split into blackheads and whiteheads. Pooled label dryness/irritation rates are incidence, not symptom magnitude; excluding side effects understates simulated burden. No transfer to other tretinoin formulations or strengths.
