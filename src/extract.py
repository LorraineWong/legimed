from __future__ import annotations

import json
import re
from typing import Any

from schema import (
    DrugInfo,
    DosageInstruction,
    FoodAction,
    FoodInteraction,
    Severity,
    SideEffect,
    Warning,
)

SEVERITY_KEYWORDS = {
    Severity.critical: ["fatal", "death", "life-threatening", "anaphylaxis", "black box"],
    Severity.high: ["serious", "severe", "hospitalization", "discontinue immediately"],
    Severity.moderate: ["moderate", "caution", "monitor closely", "may cause"],
    Severity.low: ["mild", "common", "minor", "rare"],
}

FOOD_ACTION_KEYWORDS = {
    FoodAction.avoid: ["avoid", "do not take with", "contraindicated with"],
    FoodAction.limit: ["limit", "reduce", "minimize"],
    FoodAction.take_with: ["take with food", "take with milk", "with meals"],
    FoodAction.take_without: ["take on an empty stomach", "without food"],
    FoodAction.monitor: ["monitor", "watch for", "be aware"],
}

EXTRACTION_PROMPT = """\
You are a clinical pharmacist assistant. Extract structured drug information from the medication leaflet below.

Return ONLY a JSON object with this exact schema (omit fields you cannot find):
{{
  "drug_name": "string",
  "generic_name": "string or null",
  "drug_class": "string or null",
  "indications": ["string"],
  "dosage_instructions": [{{"route": "string", "frequency": "string", "dose": "string", "notes": "string"}}],
  "side_effects": [{{"effect": "string", "severity": "low|moderate|high|critical", "frequency": "string or null"}}],
  "food_interactions": [{{"food_item": "string", "action": "avoid|limit|take_with|take_without|monitor", "reason": "string or null"}}],
  "warnings": [{{"text": "string", "severity": "low|moderate|high|critical", "relevant_conditions": ["string"]}}],
  "contraindications": ["string"],
  "storage": "string or null"
}}

LEAFLET:
{leaflet_text}

JSON:"""


def clean_food_action(action: str) -> FoodAction:
    """Map a free-text action phrase to the nearest FoodAction enum value."""
    action_lower = action.lower().strip()
    for food_action, keywords in FOOD_ACTION_KEYWORDS.items():
        if any(kw in action_lower for kw in keywords):
            return food_action
    return FoodAction.monitor


def _infer_severity(text: str) -> Severity:
    text_lower = text.lower()
    for severity, keywords in SEVERITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return severity
    return Severity.low


def _safe_severity(value: Any) -> Severity:
    try:
        return Severity(value)
    except (ValueError, TypeError):
        return Severity.low


def _safe_food_action(value: Any) -> FoodAction:
    try:
        return FoodAction(value)
    except (ValueError, TypeError):
        return clean_food_action(str(value))


def _parse_model_output(raw: str, drug_name: str) -> DrugInfo:
    """Parse JSON from model output, falling back to a minimal DrugInfo on failure."""
    json_match = re.search(r"\{[\s\S]+\}", raw)
    if not json_match:
        return DrugInfo(drug_name=drug_name)

    try:
        data: dict = json.loads(json_match.group())
    except json.JSONDecodeError:
        return DrugInfo(drug_name=drug_name)

    side_effects = [
        SideEffect(
            effect=se.get("effect", ""),
            severity=_safe_severity(se.get("severity")),
            frequency=se.get("frequency"),
        )
        for se in data.get("side_effects", [])
        if se.get("effect")
    ]

    food_interactions = [
        FoodInteraction(
            food_item=fi.get("food_item", ""),
            action=_safe_food_action(fi.get("action")),
            reason=fi.get("reason"),
        )
        for fi in data.get("food_interactions", [])
        if fi.get("food_item")
    ]

    warnings = [
        Warning(
            text=w.get("text", ""),
            severity=_safe_severity(w.get("severity")),
            relevant_conditions=w.get("relevant_conditions", []),
        )
        for w in data.get("warnings", [])
        if w.get("text")
    ]

    dosage_instructions = [
        DosageInstruction(
            route=di.get("route"),
            frequency=di.get("frequency"),
            dose=di.get("dose"),
            notes=di.get("notes"),
        )
        for di in data.get("dosage_instructions", [])
    ]

    return DrugInfo(
        drug_name=data.get("drug_name", drug_name),
        generic_name=data.get("generic_name"),
        drug_class=data.get("drug_class"),
        indications=data.get("indications", []),
        dosage_instructions=dosage_instructions,
        side_effects=side_effects,
        food_interactions=food_interactions,
        warnings=warnings,
        contraindications=data.get("contraindications", []),
        storage=data.get("storage"),
    )


def extract_drug_info_robust(leaflet_text: str, model, tokenizer) -> DrugInfo:
    """
    Run Gemma 3 inference on leaflet_text and parse the result into a DrugInfo.

    model and tokenizer must be a Hugging Face AutoModelForCausalLM /
    AutoTokenizer pair already loaded on the desired device.
    """
    import torch

    # Truncate to avoid exceeding the model's context window
    max_leaflet_chars = 6000
    truncated = leaflet_text[:max_leaflet_chars]

    prompt = EXTRACTION_PROMPT.format(leaflet_text=truncated)

    drug_name_guess = ""
    first_line = leaflet_text.strip().splitlines()[0] if leaflet_text.strip() else ""
    drug_name_guess = first_line[:80]

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=1024,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = output_ids[0][inputs["input_ids"].shape[-1]:]
    raw_output = tokenizer.decode(generated, skip_special_tokens=True)

    return _parse_model_output(raw_output, drug_name=drug_name_guess)
