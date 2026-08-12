from pydantic import BaseModel

class SkinProfileRequest(BaseModel):
    name: str
    age: int

    # Acne / clogged pores
    inflammatory_acne: int
    blackheads: int
    whiteheads: int

    # Post-acne marks / pigmentation
    pie: int
    pih: int

    # Redness / inflammation
    redness: int
    rosacea: int

    # Skin barrier / irritation
    dryness: int
    sensitivity: int
    irritation: int

    # Oil production
    oiliness: int

    # Texture / structural concerns
    texture_irregularity: int
    acne_scarring: int

    # Other common concerns
    enlarged_pores: int
    dark_circles: int
    uneven_skin_tone: int