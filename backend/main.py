from fastapi import FastAPI
from schemas import SkinProfileRequest
from models import SkinProfile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "GlassSkin backend is running"}


@app.post("/profile")
def create_profile(data: SkinProfileRequest):

    profile = SkinProfile(
        age=data.age,

        inflammatory_acne=data.inflammatory_acne,
        blackheads=data.blackheads,
        whiteheads=data.whiteheads,

        pie=data.pie,
        pih=data.pih,

        redness=data.redness,
        rosacea=data.rosacea,

        dryness=data.dryness,
        sensitivity=data.sensitivity,
        irritation=data.irritation,

        oiliness=data.oiliness,

        texture_irregularity=data.texture_irregularity,
        acne_scarring=data.acne_scarring,

        enlarged_pores=data.enlarged_pores,
        dark_circles=data.dark_circles,
        uneven_skin_tone=data.uneven_skin_tone
    )

    return profile.get_skin_summary()