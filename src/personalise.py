from __future__ import annotations

import copy

from .schema import DrugInfo, Severity, UserProfile, Warning

# Conditions that boost warning severity by one level
_CONDITION_RELEVANCE: dict[str, list[str]] = {
    "pregnant": ["pregnancy", "fetal", "teratogen", "breastfeed", "lactation", "embryo"],
    "kidney_impairment": ["renal", "kidney", "creatinine", "dialysis", "nephro"],
    "liver_impairment": ["hepatic", "liver", "cirrhosis", "jaundice", "hepato"],
    "elderly": ["elderly", "older adult", "geriatric", "aged", ">65", "over 65"],
    "child": ["pediatric", "children", "neonatal", "infant", "juvenile"],
}

_SEVERITY_ORDER = [Severity.low, Severity.moderate, Severity.high, Severity.critical]


def _bump_severity(s: Severity) -> Severity:
    idx = _SEVERITY_ORDER.index(s)
    return _SEVERITY_ORDER[min(idx + 1, len(_SEVERITY_ORDER) - 1)]


def _active_conditions(profile: UserProfile) -> list[str]:
    conditions: list[str] = [profile.age_group]
    if profile.pregnant:
        conditions.append("pregnant")
    if profile.kidney_impairment:
        conditions.append("kidney_impairment")
    if profile.liver_impairment:
        conditions.append("liver_impairment")
    return conditions


def _warning_is_relevant(warning: Warning, condition_key: str) -> bool:
    keywords = _CONDITION_RELEVANCE.get(condition_key, [])
    text_lower = warning.text.lower()
    for kw in keywords:
        if kw in text_lower:
            return True
    for rc in warning.relevant_conditions:
        if any(kw in rc.lower() for kw in keywords):
            return True
    return False


def _score_warning(warning: Warning, active_conditions: list[str]) -> tuple[int, Warning]:
    """Return (priority_score, possibly-bumped warning). Higher score = more relevant."""
    bumped = copy.copy(warning)
    relevance_hits = 0
    for cond in active_conditions:
        if _warning_is_relevant(warning, cond):
            relevance_hits += 1
            bumped = Warning(
                text=bumped.text,
                severity=_bump_severity(bumped.severity),
                relevant_conditions=bumped.relevant_conditions,
            )

    score = _SEVERITY_ORDER.index(bumped.severity) * 10 + relevance_hits
    return score, bumped


def personalise(drug_info: DrugInfo, profile: UserProfile) -> DrugInfo:
    """
    Return a new DrugInfo with warnings re-prioritised for the given UserProfile.

    Warnings relevant to the user's conditions are bumped one severity level and
    sorted to the top. Side effects and food interactions are returned unchanged.
    """
    active = _active_conditions(profile)

    scored: list[tuple[int, Warning]] = [_score_warning(w, active) for w in drug_info.warnings]
    scored.sort(key=lambda t: t[0], reverse=True)
    reprioritised_warnings = [w for _, w in scored]

    return DrugInfo(
        drug_name=drug_info.drug_name,
        generic_name=drug_info.generic_name,
        drug_class=drug_info.drug_class,
        indications=drug_info.indications,
        dosage_instructions=drug_info.dosage_instructions,
        side_effects=drug_info.side_effects,
        food_interactions=drug_info.food_interactions,
        warnings=reprioritised_warnings,
        contraindications=drug_info.contraindications,
        storage=drug_info.storage,
    )
