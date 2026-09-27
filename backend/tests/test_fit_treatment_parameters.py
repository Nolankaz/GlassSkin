"""Regression checks for the bounded Step 5 magnitude oracle."""

import json

import numpy as np
import pytest

import notes.fit_treatment_parameters as fitter
from notes.fit_treatment_parameters import EVIDENCE_DIR, UPPER_BOUNDS, fit_candidate, fit_effect


@pytest.mark.parametrize("treatment_id", ["clindamycin", "isotretinoin"])
def test_magnitude_ceiling_passes_bounded_oracle(treatment_id):
    evidence = json.loads((EVIDENCE_DIR / f"{treatment_id}.json").read_text())["effects"][0]
    times = np.asarray([row["t_days"] for row in evidence["observations"]], dtype=float)
    targets = np.asarray([row["target_points"] for row in evidence["observations"]], dtype=float)

    candidate = fit_candidate("exponential", 0, times, targets)

    assert candidate.mean_magnitude == pytest.approx(UPPER_BOUNDS[0])
    assert candidate.unconstrained_magnitude_oracle > UPPER_BOUNDS[0]
    assert "mean_magnitude_bound_hit:upper" in candidate.flags
    assert "unconstrained_magnitude_above_model_bound" in candidate.flags


def test_magnitude_ceiling_candidates_remain_in_clindamycin_search():
    evidence = json.loads((EVIDENCE_DIR / "clindamycin.json").read_text())["effects"][0]

    fitted = fit_effect("clindamycin", 1, evidence)

    assert len(fitted.magnitude_ceiling_candidates) == 3
    assert fitted.failures == ()


def test_isotretinoin_uses_best_parameter_valid_candidate():
    evidence = json.loads((EVIDENCE_DIR / "isotretinoin.json").read_text())["effects"][0]

    fitted = fit_effect("isotretinoin", 1, evidence)

    assert fitted.candidate.curve == "exponential"
    assert fitted.candidate.delay_days == 7
    assert fitted.rmse_winner.curve == "exponential"
    assert fitted.rmse_winner.delay_days == 0
    assert len(fitted.magnitude_ceiling_candidates) == 1
    assert fitted.uncertainty_ineligible_candidates == fitted.magnitude_ceiling_candidates
    assert fitted.rmse_winner == fitted.uncertainty_ineligible_candidates[0]
    assert fitted.rmse_winner.rmse < fitted.candidate.rmse


def test_bounded_oracle_still_rejects_wrong_fitted_magnitude(monkeypatch):
    monkeypatch.setattr(fitter, "curve_fit", lambda *args, **kwargs: (np.asarray([9.5, 50.0]), None))

    with pytest.raises(fitter.CandidateFailure, match="closed-form bounded magnitude oracle failed"):
        fit_candidate("linear", 0, np.asarray([10.0, 20.0]), np.asarray([5.0, 8.0]))
