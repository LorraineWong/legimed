from schema import DrugInfo, UserProfile


def personalise(drug_info: DrugInfo, profile: UserProfile) -> DrugInfo:
    """
    Re-prioritise warnings based on user health profile.
    Higher-risk warnings for this user float to the top.
    """
    priority = []
    standard = []

    for warning in drug_info.warnings:
        text_lower = warning.text.lower()
        is_priority = False

        if profile.age_group == "elderly":
            if any(w in text_lower for w in [
                "fall", "bleed", "elderly", "older", "age", "inr", "monitor"
            ]):
                is_priority = True
            if "elderly" in warning.applies_to:
                is_priority = True

        if profile.pregnant or profile.breastfeeding:
            if any(w in text_lower for w in [
                "pregnan", "fetal", "birth", "breastfeed", "lactation"
            ]):
                is_priority = True

        if profile.kidney_issue:
            if any(w in text_lower for w in ["kidney", "renal"]):
                is_priority = True

        if profile.liver_issue:
            if any(w in text_lower for w in ["liver", "hepatic"]):
                is_priority = True

        if profile.other_medications:
            for med in profile.other_medications:
                if med.lower() in text_lower:
                    is_priority = True

        if is_priority:
            priority.append(warning)
        else:
            standard.append(warning)

    drug_info.warnings = priority + standard
    return drug_info


def build_profile_context(profile: UserProfile) -> str:
    """
    Convert UserProfile into a plain English description
    for use in Gemma 4 personalisation prompt.
    """
    parts = []

    age_map = {
        "child": "a child (under 12)",
        "adult": "an adult (18–64)",
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
        meds = ", ".join(profile.other_medications)
        parts.append(f"also taking {meds}")
    if profile.allergies:
        allergies = ", ".join(profile.allergies)
        parts.append(f"with known allergies to {allergies}")

    return " ".join(parts)


def generate_personal_summary(
    drug_info: DrugInfo,
    profile: UserProfile,
    model,
    tokenizer
) -> str:
    """
    Use Gemma 4 to generate a personalised 3-sentence plain-language
    summary of the most important warnings for this specific patient.
    """
    profile_desc = build_profile_context(profile)

    # Build top warnings context
    top_warnings = drug_info.warnings[:4]
    warnings_text = "\n".join([f"- {w.text}" for w in top_warnings])

    # Build top side effects context
    high_se = [se for se in drug_info.side_effects if se.severity == "HIGH"]
    se_text = "\n".join([f"- {se.name}: {se.description}" for se in high_se[:3]])

    # Build food interactions context
    avoid_food = [fi for fi in drug_info.food_interactions if fi.action == "avoid"]
    food_text = ", ".join([fi.substance for fi in avoid_food[:3]])

    prompt = f"""You are a clinical pharmacist explaining medication to a patient in plain, simple English.

Patient: {profile_desc}
Drug: {drug_info.drug_name} ({drug_info.drug_class})

Key warnings for this patient:
{warnings_text}

Serious side effects:
{se_text}

Foods to avoid: {food_text if food_text else "none specifically noted"}

Write exactly 3 sentences:
1. The single most important thing THIS specific patient needs to know about taking this drug safely.
2. The specific risk or interaction most relevant to their profile (age, conditions, other medications).
3. One clear action they should take or avoid.

Write in plain English a patient can understand. No medical jargon. No bullet points. Just 3 sentences."""

    inputs = tokenizer(
        f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n",
        return_tensors="pt"
    ).to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=200,
        temperature=0,
        do_sample=False,
    )

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True
    ).strip()

    return response
