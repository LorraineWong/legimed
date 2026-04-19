from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FoodAction(str, Enum):
    AVOID = "avoid"
    CAUTION = "caution"
    OK = "ok"


class DosageInstruction(BaseModel):
    time_of_day: str = Field(description="morning / afternoon / evening / bedtime")
    amount: str = Field(description="e.g. 3mg, 1 tablet")
    with_food: bool = Field(description="True if must be taken with food")
    notes: Optional[str] = Field(default=None)


class SideEffect(BaseModel):
    name: str
    severity: Severity
    description: str


class FoodInteraction(BaseModel):
    substance: str
    action: FoodAction
    reason: str


class Warning(BaseModel):
    text: str
    applies_to: List[str]


class DrugInfo(BaseModel):
    drug_name: str
    active_ingredient: str
    drug_class: str
    dosage_instructions: List[DosageInstruction]
    side_effects: List[SideEffect]
    food_interactions: List[FoodInteraction]
    warnings: List[Warning]
    contraindications: List[str]
    emergency_signs: List[str]


class UserProfile(BaseModel):
    age_group: str = Field(description="child / adult / elderly")
    pregnant: bool = False
    breastfeeding: bool = False
    liver_issue: bool = False
    kidney_issue: bool = False
    other_medications: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
