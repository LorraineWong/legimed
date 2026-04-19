import json
import re
from schema import DrugInfo


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


def extract_drug_info_robust(leaflet_text: str, model, tokenizer) -> DrugInfo:
    """
    Extract DrugInfo from leaflet text using Gemma 3.
    Includes auto-correction for common output issues.
    """
    schema = json.dumps(DrugInfo.model_json_schema(), indent=2)

    prompt = f"""You are a clinical pharmacist AI. Extract medication information from the leaflet below.

STRICT RULES:
- Output ONLY valid JSON matching the schema exactly
- No markdown, no code blocks, no explanation — JSON only
- food_interactions action MUST be exactly one of: avoid, caution, ok
- side_effects severity MUST be exactly one of: HIGH, MEDIUM, LOW
- time_of_day MUST be exactly one of: morning, afternoon, evening, bedtime

JSON SCHEMA:
{schema}

LEAFLET TEXT:
{leaflet_text}

JSON OUTPUT:"""

    inputs = tokenizer(
        f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n",
        return_tensors="pt"
    ).to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=1500,
        temperature=0.1,
        do_sample=True,
    )

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True
    )

    # Clean response
    cleaned = response.strip()
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

    return DrugInfo(**data)
