import json
import re
import gc
import torch
from schema import DrugInfo, UserProfile


def clean_food_action(action: str) -> str:
    """Map any action string to valid FoodAction enum value."""
    action_lower = action.lower()
    if any(w in action_lower for w in ["avoid", "do not", "never", "stop"]):
        return "avoid"
    elif any(w in action_lower for w in [
        "caution", "limit", "monitor", "consistent",
        "affect", "interact", "inr", "reduce", "increase"
    ]):
        return "caution"
    else:
        return "ok"


def extract_and_summarise(
    leaflet_text: str,
    profile: UserProfile,
    model,
    tokenizer
) -> tuple[DrugInfo, str]:
    """
    Single Gemma 4 call that does two things at once:
    1. Extracts structured DrugInfo JSON
    2. Generates a personalised 3-sentence summary for this patient

    Returns: (DrugInfo, personal_summary_string)
    """
    schema = json.dumps(DrugInfo.model_json_schema(), indent=2)

    # Build profile description
    parts = []
    age_map = {
        "child": "a child (under 12)",
        "adult": "an adult (18-64)",
        "elderly": "a senior patient (65+)"
    }
    parts.append(age_map.get(profile.age_group, "an adult"))
    if profile.pregnant:
        parts.append("who is pregnant")
    if profile.breastfeeding:
        parts.append("who is breastfeeding")
    if profile.kidney_issue:
        parts.append("with a kidney condition")
    if profile.liver_issue:
        parts.append("with a liver condition")
    if profile.other_medications:
        parts.append(f"also taking {', '.join(profile.other_medications)}")
    if profile.allergies:
        parts.append(f"allergic to {', '.join(profile.allergies)}")
    profile_desc = " ".join(parts)

    prompt = f"""You are a clinical pharmacist AI. A patient needs help understanding their medication.

PATIENT PROFILE: {profile_desc}

TASK: Read the leaflet below and produce TWO outputs separated by the delimiter ---SUMMARY---

OUTPUT 1: Valid JSON matching this schema exactly. No markdown, no code blocks.
{schema}

OUTPUT 2: Exactly 3 plain-English sentences personalised for THIS patient:
- Sentence 1: The single most important thing this patient needs to know.
- Sentence 2: The specific risk most relevant to their profile.
- Sentence 3: One clear action they must take or avoid.
No jargon. No bullet points. Just 3 sentences.

LEAFLET TEXT:
{leaflet_text}

JSON OUTPUT:"""

    inputs = tokenizer(
        f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n",
        return_tensors="pt"
    ).to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=2000,
        temperature=0.1,
        do_sample=True,
    )

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True
    )

    # Free GPU memory immediately after inference
    del inputs, outputs
    gc.collect()
    torch.cuda.empty_cache()

    # Split into JSON and summary
    if "---SUMMARY---" in response:
        json_part, summary_part = response.split("---SUMMARY---", 1)
    else:
        json_part = response
        summary_part = ""

    # Clean JSON
    cleaned = json_part.strip()
    cleaned = re.sub(r'^```json\s*', '', cleaned)
    cleaned = re.sub(r'^```\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    data = json.loads(cleaned)

    # Auto-correct food_interactions action field
    for fi in data.get("food_interactions", []):
        if fi.get("action") not in ["avoid", "caution", "ok"]:
            fi["action"] = clean_food_action(fi.get("action", ""))

    # Auto-correct side_effects severity field
    for se in data.get("side_effects", []):
        if se.get("severity") not in ["HIGH", "MEDIUM", "LOW"]:
            se["severity"] = "MEDIUM"

    # Auto-correct time_of_day field
    valid_times = ["morning", "afternoon", "evening", "bedtime"]
    for di in data.get("dosage_instructions", []):
        if di.get("time_of_day") not in valid_times:
            di["time_of_day"] = "morning"

    drug_info = DrugInfo(**data)
    personal_summary = summary_part.strip()

    return drug_info, personal_summary


def extract_drug_info_robust(leaflet_text: str, model, tokenizer) -> DrugInfo:
    """
    Backward compatible wrapper — extracts DrugInfo only.
    Used when no profile is available.
    """
    from schema import UserProfile
    dummy_profile = UserProfile(age_group="adult")
    drug_info, _ = extract_and_summarise(
        leaflet_text, dummy_profile, model, tokenizer
    )
    return drug_info
