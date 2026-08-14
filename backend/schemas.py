from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

class SkinProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    age: int = Field(ge=0, le=120)

    # Acne / clogged pores
    inflammatory_acne: int = Field(ge=0, le=10)
    blackheads: int = Field(ge=0, le=10)
    whiteheads: int = Field(ge=0, le=10)

    # Post-acne marks / pigmentation
    pie: int = Field(ge=0, le=10)
    pih: int = Field(ge=0, le=10)

    # Redness / inflammation
    redness: int = Field(ge=0, le=10)
    rosacea: int = Field(ge=0, le=10)

    # Skin barrier / irritation
    dryness: int = Field(ge=0, le=10)
    sensitivity: int = Field(ge=0, le=10)
    irritation: int = Field(ge=0, le=10)

    # Oil production
    oiliness: int = Field(ge=0, le=10)

    # Texture / structural concerns
    texture_irregularity: int = Field(ge=0, le=10)
    acne_scarring: int = Field(ge=0, le=10)

    # Other common concerns
    enlarged_pores: int = Field(ge=0, le=10)
    dark_circles: int = Field(ge=0, le=10)
    uneven_skin_tone: int = Field(ge=0, le=10)

class SkinProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    age: Optional[int] = Field(default=None, ge=10, le=100)

    inflammatory_acne: Optional[int] = Field(default=None, ge=0, le=10)
    blackheads: Optional[int] = Field(default=None, ge=0, le=10)
    whiteheads: Optional[int] = Field(default=None, ge=0, le=10)

    pie: Optional[int] = Field(default=None, ge=0, le=10)
    pih: Optional[int] = Field(default=None, ge=0, le=10)

    redness: Optional[int] = Field(default=None, ge=0, le=10)
    rosacea: Optional[int] = Field(default=None, ge=0, le=10)

    dryness: Optional[int] = Field(default=None, ge=0, le=10)
    sensitivity: Optional[int] = Field(default=None, ge=0, le=10)
    irritation: Optional[int] = Field(default=None, ge=0, le=10)
    oiliness: Optional[int] = Field(default=None, ge=0, le=10)

    texture_irregularity: Optional[int] = Field(default=None, ge=0, le=10)
    acne_scarring: Optional[int] = Field(default=None, ge=0, le=10)
    enlarged_pores: Optional[int] = Field(default=None, ge=0, le=10)

    dark_circles: Optional[int] = Field(default=None, ge=0, le=10)
    uneven_skin_tone: Optional[int] = Field(default=None, ge=0, le=10)

class TreatmentType(str, Enum):
    topical = "topical"
    oral = "oral"
    procedural = "procedural"
    skincare = "skincare"
    other = "other"

class EvidenceSource(BaseModel):
    title: str
    url: str
    source_name: str

class ConfidenceLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"

class TreatmentOption(BaseModel):
    treatment_name: str
    treatment_type: TreatmentType

    why_it_may_fit: str

    prescription_required: bool

    key_benefits: list[str]
    key_risks: list[str]

    evidence_sources: list[EvidenceSource]

    confidence: ConfidenceLevel

class TreatmentResearchResult(BaseModel):
    options: list[TreatmentOption] = Field(
        min_length=1,
        max_length=5
    )