"""Convert a stored skin-profile row into simulation input.

The only place in the codebase that knows both the shape of a Supabase
skin_profiles row and the shape of a SkinState. Everything under
simulation/ except this module is database-agnostic.
"""

from typing import Any, Mapping

from simulation.models import SKIN_METRIC_NAMES, SkinState


class ProfileConversionError(ValueError):
    """A profile row could not be turned into a valid SkinState."""


def skin_state_from_profile(profile: Mapping[str, Any]) -> SkinState:
    """Extract the 17 skin metrics from a profile row."""

    values: dict[str, float] = {}
    missing: list[str] = []

    for name in SKIN_METRIC_NAMES:
        raw = profile.get(name)

        if raw is None:
            missing.append(name)
            continue

        values[name] = float(raw)

    if missing:
        raise ProfileConversionError(
            "Profile is missing required skin metrics: "
            + ", ".join(sorted(missing))
        )

    return SkinState(**values)