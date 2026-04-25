import json
import re
import os
import google.generativeai as genai
from schema import DrugInfo

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")


def extract_drug_info_robust(leaflet_text: str, _model=None, _processor=None) -> DrugInfo:
    """
    Extract DrugInfo from leaflet text using Gemini API.
    _model and _processor are kept for API compatibility but not used.
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
- Extract AT LEAST 3 side_effects with different severity levels and distinct descriptions.
- Extract AT LEAST 3 food_interactions. Include only actual foods, drinks, or dietary supplements.
- Extract AT LEAST 3 warnings as complete sentences.
- emergency_signs must be real medical emergencies only (e.g. severe bleeding, anaphylaxis).

JSON SCHEMA:
{schema}

LEAFLET TEXT:
{leaflet_text}

JSON OUTPUT:"""

    response = model.generate_content(prompt)
    cleaned = response.text.strip()
    cleaned = re.sub(r'^```json\s*', '', cleaned)
    cleaned = re.sub(r'^```\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    data = json.loads(cleaned)

    # Auto-correct food_interactions action
    valid_actions = ["avoid", "caution", "ok"]
    for fi in data.get("food_interactions", []):
        if fi.get("action") not in valid_actions:
            action_lower = fi.get("action", "").lower()
            if any(w in action_lower for w in ["avoid", "do not", "never"]):
                fi["action"] = "avoid"
            elif any(w in action_lower for w in ["caution", "limit", "monitor"]):
                fi["action"] = "caution"
            else:
                fi["action"] = "ok"

    # Auto-correct side_effects severity
    for se in data.get("side_effects", []):
        if se.get("severity") not in ["HIGH", "MEDIUM", "LOW"]:
            se["severity"] = "MEDIUM"

    # Auto-correct time_of_day
    valid_times = ["morning", "afternoon", "evening", "bedtime"]
    for di in data.get("dosage_instructions", []):
        if di.get("time_of_day") not in valid_times:
            di["time_of_day"] = "morning"

    # Normalise warning text
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
