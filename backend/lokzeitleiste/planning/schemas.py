from ..localization import source as _text_source
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator

PlanKind = Literal[_text_source('server_planning_schemas.text_eb8f579b6931'), _text_source('server_planning_schemas.text_35d3a889824d'), _text_source('server_planning_schemas.text_e79aa42d7d18'), _text_source('server_planning_schemas.text_52e37a639da5')]


class DayInput(BaseModel):
    date: date
    shift: Literal["standard","border_day","border_night"] | None = None
    kind: PlanKind
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def normalize_note(self):
        self.note = self.note.strip() if self.kind != _text_source('server_planning_schemas.text_52e37a639da5') else ""
        return self


class MonthInput(BaseModel):
    expected_revision: int = Field(ge=0)
    days: list[DayInput] = Field(min_length=1, max_length=31)

    @model_validator(mode="after")
    def unique_dates(self):
        if len({d.date for d in self.days}) != len(self.days):
            raise ValueError(_text_source('server_planning_schemas.text_4a71f426b3e0'))
        return self


class ImportInput(BaseModel):
    days: list[DayInput] = Field(min_length=1, max_length=366)
    expected_revisions: dict[int, int]

    @model_validator(mode="after")
    def revisions_and_dates(self):
        if len({d.date for d in self.days}) != len(self.days):
            raise ValueError(_text_source('server_planning_schemas.text_41e669688973'))
        months = {d.date.month for d in self.days}
        if set(self.expected_revisions) != months or any(v < 0 for v in self.expected_revisions.values()):
            raise ValueError(_text_source('server_planning_schemas.text_3be14794c5b9'))
        return self
