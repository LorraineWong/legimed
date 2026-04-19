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


def extract_drug_info_robust(leaflet_text: str, model, tokenizer) -> DrugInfo:
    """Extract DrugInfo from leaflet text using Gemma 4."""
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
        temperature=0,
        do_sample=False,
    )

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True
    )

    # Free GPU memory immediately
    del inputs, outputs
    gc.collect()
    torch.cuda.empty_cache()

    # Clean response
    cleaned = response.strip()
    cleaned = re.sub(r'^```json\s*', '', cleaned)
    cleaned = re.sub(r'^```\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    data = json.loads(cleaned)

    # Auto-correct fields
    for fi in data.get("food_interactions", []):
        if fi.get("action") not in ["avoid", "caution", "ok"]:
            fi["action"] = clean_food_action(fi.get("action", ""))

    for se in data.get("side_effects", []):
        if se.get("severity") not in ["HIGH", "MEDIUM", "LOW"]:
            se["severity"] = "MEDIUM"

    valid_times = ["morning", "afternoon", "evening", "bedtime"]
    for di in data.get("dosage_instructions", []):
        if di.get("time_of_day") not in valid_times:
            di["time_of_day"] = "morning"

    # Remove duplicate warnings
    seen = set()
    unique_warnings = []
    for w in data.get("warnings", []):
        if w["text"] not in seen:
            seen.add(w["text"])
            unique_warnings.append(w)
    data["warnings"] = unique_warnings

    return DrugInfo(**data)
