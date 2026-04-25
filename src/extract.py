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


def clean_amount(amount: str) -> str:
    """
    Sanitise dosage amount string.
    Removes garbled characters, keeps only the first valid dosage token.
    Examples: "762;2;AN" -> "", "2 mg to 10 mg" -> "2-10 mg", "1 tablet" -> "1 tablet"
    """
    if not amount:
        return ""

    # Keep only characters that belong in a dosage string
    cleaned = re.sub(r'[^\w\s\-\.]', ' ', amount)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Must contain at least one digit or known unit word to be valid
    if not re.search(r'\d|tablet|capsule|drop|patch|unit|ml|mg|mcg', cleaned, re.IGNORECASE):
        return ""

    # Collapse "X mg to Y mg" -> "X-Y mg"
    cleaned = re.sub(
        r'(\d+)\s*(?:mg|mcg|ml)\s+to\s+(\d+\s*(?:mg|mcg|ml))',
        lambda m: m.group(0).replace(' to ', '-'),
        cleaned, flags=re.IGNORECASE
    )

    return cleaned[:30]  # hard cap — no dosage string should be longer than this


def extract_drug_info_robust(leaflet_text: str, model, tokenizer) -> DrugInfo:
    """
    Extract DrugInfo from leaflet text using Gemma 4.
    Prompt enforces minimum content requirements and clean formatting.
    """
    schema = json.dumps(DrugInfo.model_json_schema(), indent=2)

    prompt = f"""You are a clinical pharmacist AI. Extract medication information from the leaflet below.

STRICT OUTPUT RULES:
- Output ONLY valid JSON matching the schema. No markdown, no code blocks, no explanation.
- food_interactions action MUST be exactly one of: avoid, caution, ok
- side_effects severity MUST be exactly one of: HIGH, MEDIUM, LOW
- time_of_day MUST be exactly one of: morning, afternoon, evening, bedtime
- amount MUST be a clean dosage string like "5 mg", "1 tablet", "2-10 mg". No garbled text.
- warning text MUST be a complete readable sentence in plain English. Never ALL CAPS only.
- Extract AT LEAST 3 side_effects if mentioned anywhere in the leaflet.
- Extract AT LEAST 3 food_interactions if mentioned anywhere in the leaflet. food_interactions must only include actual foods, drinks, beverages, or dietary supplements (e.g. alcohol, grapefruit, milk, vitamin K, caffeine). Do NOT include other medications or drugs as food_interactions — drug interactions belong in warnings only.
- Extract AT LEAST 3 warnings if mentioned anywhere in the leaflet.

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
        max_new_tokens=1200,
        temperature=0,
        do_sample=False,
    )

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True
    )

    del inputs, outputs
    gc.collect()
    torch.cuda.empty_cache()

    # Strip markdown fences if present
    cleaned = response.strip()
    cleaned = re.sub(r'^```json\s*', '', cleaned)
    cleaned = re.sub(r'^```\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    data = json.loads(cleaned)

    # Auto-correct food_interactions action
    for fi in data.get("food_interactions", []):
        if fi.get("action") not in ["avoid", "caution", "ok"]:
            fi["action"] = clean_food_action(fi.get("action", ""))

    # Auto-correct side_effects severity
    for se in data.get("side_effects", []):
        if se.get("severity") not in ["HIGH", "MEDIUM", "LOW"]:
            se["severity"] = "MEDIUM"

    # Auto-correct time_of_day
    valid_times = ["morning", "afternoon", "evening", "bedtime"]
    for di in data.get("dosage_instructions", []):
        if di.get("time_of_day") not in valid_times:
            di["time_of_day"] = "morning"
        # Clean amount field
        di["amount"] = clean_amount(di.get("amount", ""))

    # Normalise warning text: sentence-case if ALL CAPS
    for w in data.get("warnings", []):
        text = w.get("text", "")
        if text == text.upper() and len(text) > 3:
            w["text"] = text.capitalize()

    # Remove duplicate warnings
    seen = set()
    unique_warnings = []
    for w in data.get("warnings", []):
        if w["text"] not in seen:
            seen.add(w["text"])
            unique_warnings.append(w)
    data["warnings"] = unique_warnings

    return DrugInfo(**data)
