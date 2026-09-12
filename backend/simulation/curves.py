"""Map elapsed time to the fraction of an effect's full magnitude realised.

The fraction is dimensionless and lives in the closed interval [0, 1]. This
module contains no medical values: its numbers are pure mathematics, and
per-treatment parameters arrive later with documented sources.
"""

import math
from typing import Callable

from simulation.models import CURVES_WITHOUT_DELAY, TimeCurveType


# The closed range every returned progress fraction must remain within.
PROGRESS_MIN = 0.0
PROGRESS_MAX = 1.0

# The logistic's steepness is LOGISTIC_STEEPNESS / time_scale_days, so its
# shape is scale-free. This value keeps the raw value at the gate small
# (~0.018), so renormalisation barely distorts the sigmoid.
LOGISTIC_STEEPNESS = 4.0


class UnknownTimeCurveError(ValueError):
    """The requested time-curve name is not supported."""


def linear_progress(elapsed_days: float, time_scale_days: float) -> float:
    """Return linear progress after the delay gate."""

    x = elapsed_days / time_scale_days
    return min(x, 1.0)


def exponential_progress(elapsed_days: float, time_scale_days: float) -> float:
    """Return saturating exponential progress after the delay gate."""

    x = elapsed_days / time_scale_days
    # For very small x, exp(-x) rounds to exactly 1.0 and the naive subtraction
    # catastrophically cancels to 0.0; expm1 remains accurate near zero.
    return -math.expm1(-x)


def logistic_progress(elapsed_days: float, time_scale_days: float) -> float:
    """Return renormalised logistic progress after the delay gate."""

    k = LOGISTIC_STEEPNESS / time_scale_days
    u0 = time_scale_days
    # The raw logistic is ~0.018 at u == 0, creating a visible discontinuity
    # when the delay ends. Shifting and rescaling removes it while preserving
    # monotonicity and the asymptote at 1. With u0 == time_scale_days, the
    # exponent at u == 0 is always exactly LOGISTIC_STEEPNESS, so math.exp
    # cannot overflow under this parameterisation regardless of the time scale.
    initial = 1.0 / (1.0 + math.exp(k * u0))
    value = 1.0 / (1.0 + math.exp(-k * (elapsed_days - u0)))
    return (value - initial) / (1.0 - initial)


# Linear and delayed_linear share one shape; they differ only in whether a
# non-zero delay is permitted. A test asserts this registry covers
# get_args(TimeCurveType) exactly, so adding a Literal name without an
# implementation fails the suite.
CURVE_FUNCTIONS: dict[TimeCurveType, Callable[[float, float], float]] = {
    "linear": linear_progress,
    "delayed_linear": linear_progress,
    "exponential": exponential_progress,
    "logistic": logistic_progress,
}


def progress(curve: TimeCurveType, t_days: float, delay_days: float, time_scale_days: float) -> float:
    """Return the dimensionless fraction of an effect realised at ``t_days``.

    For linear curves, ``time_scale_days`` is the time after the delay needed
    to reach full effect. For exponential curves, it is the e-folding time.
    For logistic curves, it sets the raw sigmoid's midpoint and scale.

    Raises ``UnknownTimeCurveError`` for an unsupported curve and ``ValueError``
    for non-finite values, invalid times or scales, or a disallowed delay.
    """

    if curve not in CURVE_FUNCTIONS:
        valid_names = ", ".join(sorted(CURVE_FUNCTIONS))
        raise UnknownTimeCurveError(f"Unknown time curve {curve!r}; valid names are: {valid_names}")

    # NaN passes ordinary comparison guards silently and then propagates
    # through every downstream computation, so finiteness needs an explicit check.
    if not all(math.isfinite(value) for value in (t_days, delay_days, time_scale_days)):
        raise ValueError("t_days, delay_days, and time_scale_days must all be finite")

    if t_days < 0 or delay_days < 0:
        raise ValueError("t_days and delay_days must be non-negative")
    if time_scale_days <= 0:
        raise ValueError("time_scale_days must be greater than zero")
    # CURVES_WITHOUT_DELAY lives in models.py so the model validator and this
    # guard share one definition.
    if delay_days > 0 and curve in CURVES_WITHOUT_DELAY:
        raise ValueError("linear means no latency and requires delay_days == 0; use delayed_linear when a non-zero delay is needed")

    # Applying the delay gate here once makes progress exactly 0 for t <= delay
    # for every curve structurally, rather than as four separate promises.
    elapsed = max(t_days - delay_days, 0.0)
    result = CURVE_FUNCTIONS[curve](elapsed, time_scale_days)

    # This single-point clamp defends against floating-point overshoot, matching
    # the engine rule that a range invariant is enforced at one boundary.
    return min(max(result, PROGRESS_MIN), PROGRESS_MAX)
