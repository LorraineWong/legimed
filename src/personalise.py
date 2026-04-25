from schema import DrugInfo, UserProfile
import re


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

        if profile.heart_condition:
            if any(w in text_lower for w in ["heart", "cardiac", "cardiovascular", "arrhythmia"]):
                is_priority = True

        if profile.diabetes:
            if any(w in text_lower for w in ["diabetes", "diabetic", "glucose", "blood sugar", "insulin"]):
                is_priority = True

        if profile.hypertension:
            if any(w in text_lower for w in ["blood pressure", "hypertension", "hypotension"]):
                is_priority = True

        if profile.asthma:
            if any(w in text_lower for w in ["asthma", "bronchospasm", "respiratory", "breathing"]):
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
    """Convert UserProfile into a plain English description."""
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
        meds = ", ".join(profile.other_medications)
        parts.append(f"also taking {meds}")
    if profile.allergies:
        allergies = ", ".join(profile.allergies)
        parts.append(f"with known allergies to {allergies}")

    return " ".join(parts)


def _safe_amount(amount: str) -> str:
    """
    Return amount only if it looks like a valid dosage string.
    Prevents garbled Gemma output from appearing in the summary sentence.
    """
    if not amount:
        return ""
    # Must contain a digit or a known dosage word
    if not re.search(r'\d|tablet|capsule|drop|patch|unit', amount, re.IGNORECASE):
        return ""
    # Must not be suspiciously long or contain semicolons / slashes
    if len(amount) > 20 or any(c in amount for c in [';', '/', '\\']):
        return ""
    return amount


def generate_personal_summary(drug_info: DrugInfo, profile: UserProfile) -> str:
    """
    Generate a personalised plain-English 3-sentence summary using Python logic.
    No second AI call — saves GPU memory and is fully deterministic.
    """
    lines = []

    # Sentence 1: dosage fact
    if drug_info.dosage_instructions:
        d = drug_info.dosage_instructions[0]
        amount = _safe_amount(d.amount)
        food_str = "with food" if d.with_food else "without food"
        if amount:
            lines.append(
                f"Take {amount} of {drug_info.drug_name} every {d.time_of_day}, "
                f"{food_str}, at the same time each day."
            )
        else:
            lines.append(
                f"Take {drug_info.drug_name} every {d.time_of_day}, "
                f"{food_str}, at the same time each day."
            )

    # Sentence 2: most relevant risk for this profile
    risk_parts = []
    if profile.age_group == "elderly":
        risk_parts.append("as a senior patient, fall-related bleeding is a serious concern")
    if profile.kidney_issue:
        risk_parts.append("your kidney condition may affect how this drug is processed")
    if profile.heart_condition:
        risk_parts.append("your heart condition requires careful monitoring with this drug")
    if profile.diabetes:
        risk_parts.append("monitor your blood sugar levels closely while taking this drug")
    if profile.hypertension:
        risk_parts.append("this drug may affect your blood pressure")
    if profile.pregnant:
        risk_parts.append("this drug may not be safe during pregnancy — confirm with your doctor immediately")
    if profile.other_medications:
        meds = ", ".join(profile.other_medications[:2])
        risk_parts.append(f"taking {meds} alongside this drug requires careful monitoring")

    if risk_parts:
        lines.append("Important for you: " + "; ".join(risk_parts) + ".")
    elif drug_info.warnings:
        # Use first warning but ensure it ends with a period
        w_text = drug_info.warnings[0].text.strip()
        if not w_text.endswith("."):
            w_text += "."
        lines.append(w_text)

    # Sentence 3: key food warning or emergency sign
    avoid_foods = [fi.substance for fi in drug_info.food_interactions if fi.action == "avoid"]
    if avoid_foods:
        food_str = ", ".join(avoid_foods[:2])
        lines.append(f"Avoid {food_str} while taking this medication.")
    elif drug_info.emergency_signs:
        lines.append(
            f"Seek emergency help immediately if you experience: {drug_info.emergency_signs[0]}."
        )

    return " ".join(lines)
