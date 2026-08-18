import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from schemas import TreatmentResearchResult

class TreatmentResearchError(Exception):
    pass

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY is not configured"
    )

client = AsyncOpenAI(api_key=api_key)


TRUSTED_MEDICAL_DOMAINS = [
    # U.S. biomedical literature + government
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "nih.gov",
    "fda.gov",
    "clinicaltrials.gov",

    # Dermatology-specific professional guidance
    "aad.org",

    # High-quality international clinical guidelines
    "nice.org.uk",
]

RESEARCH_VERSION = "v1"

TREATMENT_RESEARCH_INSTRUCTIONS = """
You are the medical research layer for GlassSkinAI.

Your task is to analyze the supplied digital skin profile and identify up to
three evidence-supported acne treatment options worth considering.

You may only use evidence found through the provided web search tool.

Only use these professional medical sources:
- PubMed / NCBI
- American Academy of Dermatology
- U.S. Food and Drug Administration
- ClinicalTrials.gov
- National Institutes of Health
- National Institute for Health and Care Excellence

For each treatment option:
- explain why it may be relevant to the profile
- identify important benefits
- identify important risks or limitations
- indicate whether it requires a prescription
- provide supporting source URLs
- state confidence as low, moderate, or high

Do not invent efficacy percentages.
Do not claim certainty.
Do not prescribe medication.
Return evidence-grounded options for consideration.
"""

def build_profile_context(profile: dict) -> str:
    return f"""
Digital skin profile

Age: {profile["age"]}
Gender: {profile.get("gender", "Not specified")}

Acne:
- Inflammatory acne: {profile["inflammatory_acne"]}/10
- Cystic / nodular acne: {profile.get("cystic_nodular_acne", 0)}/10
- Blackheads: {profile["blackheads"]}/10
- Whiteheads: {profile["whiteheads"]}/10

Pigmentation / redness:
- PIE: {profile["pie"]}/10
- PIH: {profile["pih"]}/10
- Redness: {profile["redness"]}/10

Skin barrier / sensitivity:
- Dryness: {profile["dryness"]}/10
- Sensitivity: {profile["sensitivity"]}/10
- Irritation: {profile["irritation"]}/10
- Oiliness: {profile["oiliness"]}/10

Other skin characteristics:
- Rosacea: {profile["rosacea"]}/10
- Texture irregularity: {profile["texture_irregularity"]}/10
- Acne scarring: {profile["acne_scarring"]}/10
- Enlarged pores: {profile["enlarged_pores"]}/10
- Dark circles: {profile["dark_circles"]}/10
- Uneven skin tone: {profile["uneven_skin_tone"]}/10
"""

async def generate_treatment_options(profile: dict,) -> TreatmentResearchResult:

    profile_text = build_profile_context(profile)

    try:
        response = await client.responses.parse(
            model="gpt-5-mini",
            instructions=TREATMENT_RESEARCH_INSTRUCTIONS,

            tools=[
                {
                    "type": "web_search",
                    "filters": {
                        "allowed_domains": TRUSTED_MEDICAL_DOMAINS
                    },
                    "search_context_size": "low",
                }
            ],

            input=profile_text,

            text_format=TreatmentResearchResult,
        )
    
    except Exception as error:
        raise TreatmentResearchError("Treatment research failed") from error

    result = response.output_parsed

    if result is None:
        raise TreatmentResearchError(
            "No structured treatment result was returned"
        )

    return result
