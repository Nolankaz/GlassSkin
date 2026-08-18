from fastapi import FastAPI, HTTPException
from schemas import SkinProfileRequest, SkinProfileUpdate
from models import SkinProfile
from fastapi.middleware.cors import CORSMiddleware
from database import supabase
from services.treatment_research import (
    RESEARCH_VERSION,
    generate_treatment_options,
    TreatmentResearchError,
)
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "GlassSkin backend is running"}


@app.get("/profiles")
def get_profiles():
    response = (
        supabase
        .table("skin_profiles")
        .select("*")
        .execute()
    )

    return response.data
 

@app.get("/profiles/{profile_id}")
def get_profile(profile_id: int):
    response = (
        supabase
        .table("skin_profiles")
        .select("*")
        .eq("id", profile_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    return response.data[0]


@app.post("/profile")
def create_profile(data: SkinProfileRequest):

    profile = SkinProfile(
        age=data.age,
        gender=data.gender,

        inflammatory_acne=data.inflammatory_acne,
        cystic_nodular_acne=data.cystic_nodular_acne,
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

    profile_data = {
        "name": data.name,
        "age": profile.age,
        "gender": profile.gender,
        "inflammatory_acne": profile.inflammatory_acne,
        "cystic_nodular_acne": profile.cystic_nodular_acne,
        "blackheads": profile.blackheads,
        "whiteheads": profile.whiteheads,
        "pie": profile.pie,
        "pih": profile.pih,
        "redness": profile.redness,
        "rosacea": profile.rosacea,
        "dryness": profile.dryness,
        "sensitivity": profile.sensitivity,
        "irritation": profile.irritation,
        "oiliness": profile.oiliness,
        "texture_irregularity": profile.texture_irregularity,
        "acne_scarring": profile.acne_scarring,
        "enlarged_pores": profile.enlarged_pores,
        "dark_circles": profile.dark_circles,
        "uneven_skin_tone": profile.uneven_skin_tone,
    }

    response = (
        supabase
        .table("skin_profiles")
        .insert(profile_data)
        .execute()
    )

    return response.data[0]

@app.patch("/profiles/{profile_id}")
def update_profile(profile_id: int, data: SkinProfileUpdate):
    update_data = data.model_dump(exclude_unset=True)

    response = (
        supabase
        .table("skin_profiles")
        .update(update_data)
        .eq("id", profile_id)
        .select("*")
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    if update_data:
        try:
            (
                supabase
                .table("treatment_research_results")
                .delete()
                .eq("profile_id", profile_id)
                .execute()
            )
        except Exception as error:
            print("Failed to clear saved treatment research", error)

    return response.data[0]

def get_saved_treatment_research(profile_id: int):
    try:
        response = (
            supabase
            .table("treatment_research_results")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("research_version", RESEARCH_VERSION)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as error:
        print("Failed to load saved treatment research", error)
        return None

    if not response.data:
        return None

    return response.data[0]["result"]

@app.get("/profiles/{profile_id}/treatment-options/saved")
def get_saved_treatment_options(profile_id: int):
    saved_result = get_saved_treatment_research(profile_id)

    return {
        "profile_id": profile_id,
        "result": saved_result,
        "research_version": RESEARCH_VERSION,
    }

@app.get("/profiles/{profile_id}/treatment-options")
async def get_treatment_options(profile_id: int):
    response = (
        supabase
        .table("skin_profiles")
        .select("*")
        .eq("id", profile_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    profile = response.data[0]
    saved_result = get_saved_treatment_research(profile_id)

    if saved_result is not None:
        return {
            "profile_id": profile_id,
            "result": saved_result,
            "research_version": RESEARCH_VERSION,
        }

    try:
        result = await generate_treatment_options(profile)

    except TreatmentResearchError:
        raise HTTPException(
            status_code=502,
            detail="Unable to research treatment options"
        )

    result_data = result.model_dump(mode="json")

    try:
        (
            supabase
            .table("treatment_research_results")
            .insert({
                "profile_id": profile_id,
                "research_version": RESEARCH_VERSION,
                "result": result_data,
            })
            .execute()
        )
    except Exception as error:
        print("Failed to save treatment research", error)

    return {
        "profile_id": profile_id,
        "result": result_data,
        "research_version": RESEARCH_VERSION,
    }
