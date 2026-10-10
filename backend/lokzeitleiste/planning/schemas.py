from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator

PlanKind = Literal["Arbeitstag", "Urlaub", "Ruhetag", "Ungeplant"]


class DayInput(BaseModel):
    date: date
    shift: Literal["standard","border_day","border_night"] | None = None
    kind: PlanKind
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def normalize_note(self):
        self.note = self.note.strip() if self.kind != "Ungeplant" else ""
        return self


class MonthInput(BaseModel):
    expected_revision: int = Field(ge=0)
    days: list[DayInput] = Field(min_length=1, max_length=31)

    @model_validator(mode="after")
    def unique_dates(self):
        if len({d.date for d in self.days}) != len(self.days):
            raise ValueError("Jedes Datum darf nur einmal vorkommen")
        return self


class ImportInput(BaseModel):
    days: list[DayInput] = Field(min_length=1, max_length=366)
    expected_revisions: dict[int, int]

    @model_validator(mode="after")
    def revisions_and_dates(self):
        if len({d.date for d in self.days}) != len(self.days):
            raise ValueError("Doppelte Datumsangabe")
        months = {d.date.month for d in self.days}
        if set(self.expected_revisions) != months or any(v < 0 for v in self.expected_revisions.values()):
            raise ValueError("Revisionsstände aller betroffenen Monate erforderlich")
        return self
