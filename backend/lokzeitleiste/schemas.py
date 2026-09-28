from datetime import date, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


FederalState = Literal["BB", "BE", "BW", "BY", "HB", "HE", "HH", "MV", "NI", "NW", "RP", "SH", "SL", "SN", "ST", "TH"]


EntryKind = Literal["Rufbereitschaft", "Bereitschaft", "Zugfahrt", "Ausfallschicht", "Krank", "Urlaub", "Sonstige Erfassung"]


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str


class TfCreate(Credentials):
    password: str = Field(min_length=12)
    last_name: str = Field(min_length=1, max_length=120)
    first_name: str = Field(min_length=1, max_length=120)
    personnel_number: str = Field(min_length=1, max_length=40)
    target_hours_minutes: int = Field(ge=0, le=744 * 60)
    vacation_days: int = Field(ge=0, le=366)
    birth_date: date
    bahncard: Literal[50, 100]
    email: EmailStr
    federal_state: FederalState


class TfDeliveryUpdate(BaseModel):
    email: EmailStr
    federal_state: FederalState


class EntryIn(BaseModel):
    client_id: UUID
    kind: EntryKind
    date: date
    start: time
    end: time
    pause: int = Field(ge=0, le=1440)
    guest: int = Field(ge=0, le=1440)
    note: str = Field(default="", max_length=2000)
    away: bool = False
    accommodation: Literal["", "Dienstwohnung", "Hotel"] = ""
    hotel_name: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def validate_times(self):
        if (self.start.second or self.end.second or self.start.microsecond or self.end.microsecond
                or self.start.tzinfo or self.end.tzinfo):
            raise ValueError("Uhrzeiten müssen lokale Stunden und Minuten ohne Sekunden enthalten")
        begin = self.start.hour * 60 + self.start.minute
        finish = self.end.hour * 60 + self.end.minute
        span = finish - begin if finish > begin else finish + 1440 - begin
        if self.kind == "Rufbereitschaft":
            if begin < 480 or finish > 1200 or finish <= begin or span > 480:
                raise ValueError("Rufbereitschaft: 08:00–20:00 Uhr, höchstens acht Stunden")
        elif self.kind == "Bereitschaft" and span > 480:
            raise ValueError("Bereitschaft: vorläufig höchstens acht Stunden")
        if self.kind in ("Rufbereitschaft", "Bereitschaft"):
            if self.pause or self.guest or self.note:
                raise ValueError("Bereitschaft enthält nur Zeitraum und Unterkunft")
            if self.away and (not self.accommodation or (self.accommodation == "Hotel" and not self.hotel_name.strip())):
                raise ValueError("Auswärtige Bereitschaft benötigt Unterkunft und ggf. Hotelnamen")
            if not self.away and (self.accommodation or self.hotel_name):
                raise ValueError("Unterkunft nur bei auswärtigem Aufenthalt")
        elif self.away or self.accommodation or self.hotel_name:
            raise ValueError("Unterkunft ist derzeit nur bei Bereitschaft erfasst")
        elif self.pause >= span or self.guest > span - self.pause:
            raise ValueError("Pause und Gastfahrt müssen in den Zeitraum passen")
        return self


class EntryBatch(BaseModel):
    entries: list[EntryIn] = Field(max_length=500)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [entry.client_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("client_id darf im selben Paket nur einmal vorkommen")
        return self
