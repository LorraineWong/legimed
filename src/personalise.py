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
