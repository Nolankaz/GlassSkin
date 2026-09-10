"""Tests for the Supabase row -> SkinState boundary."""

import pytest

from pydantic import ValidationError

from simulation.models import SKIN_METRIC_NAMES
from simulation.profile_adapter import (
    ProfileConversionError,
    skin_state_from_profile,
)


def profile_row(**overrides):
    """A row shaped like what supabase.table('skin_profiles').select('*') returns."""

    row = {
        "id": 3,
        "created_at": "2026-01-15T10:30:00+00:00",
        "name": "Test Profile",
        "age": 21,
        "gender": "Not specified",
        **{metric: 4 for metric in SKIN_METRIC_NAMES},
    }

    row.update(overrides)
    return row


def test_converts_a_complete_row():
    state = skin_state_from_profile(
        profile_row(redness=8, oiliness=2)
    )

    assert state.redness == 8.0
    assert state.oiliness == 2.0


def test_ignores_non_metric_columns():
    """id/name/age/gender must not reach SkinState, which forbids extras."""

    state = skin_state_from_profile(profile_row())

    assert not hasattr(state, "age")
    assert set(state.model_dump()) == set(SKIN_METRIC_NAMES)


def test_null_cystic_acne_raises():
    """cystic_nodular_acne is NOT NULL DEFAULT 0 in the live database, so a
    NULL is a data problem rather than an older row to be tolerated.
    """

    with pytest.raises(
        ProfileConversionError,
        match="cystic_nodular_acne",
    ):
        skin_state_from_profile(
            profile_row(cystic_nodular_acne=None)
        )


def test_missing_required_metric_raises_and_names_it():
    row = profile_row()

    del row["redness"]

    with pytest.raises(
        ProfileConversionError,
        match="redness",
    ):
        skin_state_from_profile(row)


def test_reports_every_missing_metric_at_once():
    row = profile_row()

    del row["redness"]
    del row["dryness"]

    with pytest.raises(ProfileConversionError) as excinfo:
        skin_state_from_profile(row)

    assert "redness" in str(excinfo.value)
    assert "dryness" in str(excinfo.value)


def test_null_in_any_metric_raises():
    """Every metric column is NOT NULL in the live database; no metric has a
    legacy-NULL exemption.
    """

    with pytest.raises(
        ProfileConversionError,
        match="redness",
    ):
        skin_state_from_profile(
            profile_row(redness=None)
        )


def test_out_of_range_value_raises_validation_error():
    """Range enforcement belongs to SkinState, so this is Pydantic's error."""

    with pytest.raises(ValidationError):
        skin_state_from_profile(profile_row(redness=99))