from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    critical = "critical"


class FoodAction(str, Enum):
    avoid = "avoid"
    limit = "limit"
    take_with = "take_with"
    take_without = "take_without"
    monitor = "monitor"


class DosageInstruction(BaseModel):
    route: Optional[str] = None
    frequency: Optional[str] = None
    dose: Optional[str] = None
    notes: Optional[str] = None


class SideEffect(BaseModel):
    effect: str
    severity: Severity
    frequency: Optional[str] = None


class FoodInteraction(BaseModel):
    food_item: str
    action: FoodAction
    reason: Optional[str] = None


class Warning(BaseModel):
    text: str
    severity: Severity
    relevant_conditions: List[str] = Field(default_factory=list)


class DrugInfo(BaseModel):
    drug_name: str
    generic_name: Optional[str] = None
    drug_class: Optional[str] = None
    indications: List[str] = Field(default_factory=list)
    dosage_instructions: List[DosageInstruction] = Field(default_factory=list)
    side_effects: List[SideEffect] = Field(default_factory=list)
    food_interactions: List[FoodInteraction] = Field(default_factory=list)
    warnings: List[Warning] = Field(default_factory=list)
    contraindications: List[str] = Field(default_factory=list)
    storage: Optional[str] = None


class UserProfile(BaseModel):
    age_group: str  # "child", "adult", "elderly"
    pregnant: bool = False
    kidney_impairment: bool = False
    liver_impairment: bool = False
    other_medications: List[str] = Field(default_factory=list)
