"""Load only this package's read-only calibrated treatment data.

This is simulation's sole filesystem boundary. No caller-provided path or
environment value is used to find parameter files.
"""

import json
import re
from importlib import resources

from pydantic import ValidationError

from simulation.models import TreatmentParameters


PARAMETER_VERSION_PATTERN = r"^v[0-9]+$"


class ParameterLoadError(ValueError):
    """Packaged treatment parameters are missing or invalid."""


def available_versions() -> tuple[str, ...]:
    package = resources.files("simulation.parameters")
    return tuple(sorted(entry.name for entry in package.iterdir() if entry.is_dir() and re.fullmatch(PARAMETER_VERSION_PATTERN, entry.name)))


def load_treatment_parameters(version: str) -> tuple[TreatmentParameters, ...]:
    if not isinstance(version, str) or not re.fullmatch(PARAMETER_VERSION_PATTERN, version):
        raise ParameterLoadError(f"invalid parameter version {version!r}; expected {PARAMETER_VERSION_PATTERN}")

    directory = resources.files("simulation.parameters").joinpath(version)
    if not directory.is_dir():
        raise ParameterLoadError(f"parameter version {version!r} is unavailable; available versions: {available_versions()}")
    files = sorted((entry for entry in directory.iterdir() if entry.is_file() and entry.name.endswith(".json")), key=lambda entry: entry.name)
    if not files:
        raise ParameterLoadError(f"parameter version {version!r} contains no JSON treatment files")

    loaded = []
    filenames_by_id = {}
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ParameterLoadError(f"invalid JSON in {file.name}: {exc}") from exc
        if isinstance(data, dict) and isinstance(data.get("effects"), list):
            for effect in data["effects"]:
                if isinstance(effect, dict) and isinstance(effect.get("provenance"), dict):
                    kind = effect["provenance"].get("kind")
                    if kind is not None and kind != "published":
                        raise ParameterLoadError(f"parameter file {file.name} effect {effect.get('target_metric')!r} has provenance kind {kind!r}; expected 'published'")
        try:
            treatment = TreatmentParameters.model_validate(data)
        except ValidationError as exc:
            raise ParameterLoadError(f"invalid treatment parameters in {file.name}: {exc}") from exc

        previous = filenames_by_id.get(treatment.treatment_id)
        if previous is not None:
            raise ParameterLoadError(f"duplicate treatment_id {treatment.treatment_id!r} in {previous} and {file.name}")
        stem = file.name[:-5]
        if stem != treatment.treatment_id:
            raise ParameterLoadError(f"parameter filename {file.name} has stem {stem!r}, but treatment_id is {treatment.treatment_id!r}")
        if treatment.parameter_version != version:
            raise ParameterLoadError(f"parameter file {file.name} declares parameter_version {treatment.parameter_version!r}, but directory version is {version!r}")
        for effect in treatment.effects:
            if effect.provenance.kind != "published":
                raise ParameterLoadError(f"parameter file {file.name} effect {effect.target_metric} has provenance kind {effect.provenance.kind!r}; expected 'published'")
        filenames_by_id[treatment.treatment_id] = file.name
        loaded.append(treatment)

    return tuple(sorted(loaded, key=lambda treatment: treatment.treatment_id))


def available_treatment_ids(version: str) -> tuple[str, ...]:
    return tuple(treatment.treatment_id for treatment in load_treatment_parameters(version))


def load_treatment(treatment_id: str, version: str) -> TreatmentParameters:
    treatments = load_treatment_parameters(version)
    for treatment in treatments:
        if treatment.treatment_id == treatment_id:
            return treatment
    valid_ids = tuple(treatment.treatment_id for treatment in treatments)
    raise ParameterLoadError(f"treatment_id {treatment_id!r} is unavailable in version {version!r}; valid ids: {valid_ids}")
