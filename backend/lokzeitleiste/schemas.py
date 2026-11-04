from .localization import source as _text_source
from datetime import date, time, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator, field_validator


FederalState = Literal["BB", "BE", "BW", "BY", "HB", "HE", "HH", "MV", "NI", "NW", "RP", "SH", "SL", "SN", "ST", "TH"]


EntryKind = Literal[_text_source('server_schemas.text_bfe022ddd1f8'), _text_source('server_schemas.text_a88b0d6dfef3'), _text_source('server_schemas.text_52c5d4a0445b'), _text_source('server_schemas.text_98a9c4972272'), _text_source('server_schemas.text_be1600b499c6'), _text_source('server_schemas.text_35d3a889824d'), _text_source('server_schemas.text_f31b8681bfca')]


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str



class TfAddressIn(BaseModel):
    street: str = Field(min_length=1, max_length=200)
    house_number: str = Field(min_length=1, max_length=30)
    postal_code: str = Field(min_length=1, max_length=20)
    city: str = Field(min_length=1, max_length=120)
    federal_state: FederalState
    is_postal: bool = False

    @field_validator('street', 'house_number', 'postal_code', 'city')
    @classmethod
    def clean(cls, value):
        if not value.strip(): raise ValueError(_text_source('server_schemas.text_a54f48a13bbb'))
        return value.strip()


class TfDetails(BaseModel):
    @field_validator('gender',mode='before')
    @classmethod
    def normalize_gender(cls,value):
        return {_text_source('server_schemas.text_c1e0a9a9f71d'):'male','weiblich':'female','divers':'diverse',_text_source('server_schemas.text_3e0b1cbc7525'):'unspecified'}.get(value,value) if isinstance(value,str) else value

    gender: Literal["male","female","diverse","unspecified"] | None = None
    weekly_minutes: int | None = Field(default=None, ge=0, le=168*60)
    entry_date: date | None = None
    exit_date: date | None = None
    immediate_block: bool | None = None
    nationality: str | None = Field(default=None, pattern=r'^[A-Z]{2}$')
    home_station: str | None = Field(default=None, max_length=10)
    addresses: list[TfAddressIn] | None = Field(default=None, min_length=1, max_length=10)

    @model_validator(mode='after')
    def postal_address(self):
        if self.addresses is not None:
            if len(self.addresses) == 1: self.addresses[0].is_postal = True
            if sum(a.is_postal for a in self.addresses) != 1:
                raise ValueError(_text_source('server_schemas.text_c48c100d178f'))
        if self.entry_date and self.exit_date and self.exit_date < self.entry_date:
            raise ValueError(_text_source('server_schemas.text_547153433a04'))
        return self


class TfCreate(Credentials, TfDetails):
    username: str = Field(pattern=r"^[1-9][0-9]{5}$", coerce_numbers_to_str=True)
    driver_type: Literal["route","border","both"] = "route"
    password: str = Field(min_length=6)
    photo_base64: str | None = Field(default=None,max_length=6990510)
    last_name: str = Field(min_length=1, max_length=120)
    first_name: str = Field(min_length=1, max_length=120)
    personnel_number: str = Field(min_length=1, max_length=40)
    target_hours_minutes: int = Field(default=0, ge=0, le=744 * 60)
    vacation_days: int = Field(ge=0, le=366)
    birth_date: date
    bahncard: Literal[0, 50, 100]
    bahncard_valid_until: date | None = None
    email: EmailStr
    federal_state: FederalState = "BE"


class TfDeliveryUpdate(BaseModel):
    email: EmailStr
    federal_state: FederalState


class EntryIn(BaseModel):
    client_id: UUID
    kind: EntryKind
    date: date
    end_date: date | None = None
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
            raise ValueError(_text_source('server_schemas.text_28bd63ce0341'))
        begin = self.start.hour * 60 + self.start.minute
        finish = self.end.hour * 60 + self.end.minute
        if self.end_date is not None:
            if self.end_date<self.date or not 2000<=self.date.year<=self.end_date.year<=2100:
                raise ValueError(_text_source('server_schemas.text_d06749bae264'))
            span=(self.end_date-self.date).days*1440+finish-begin
            if span<=0:raise ValueError(_text_source('server_schemas.text_650e910feb9c'))
            if self.kind in (_text_source('server_schemas.text_35d3a889824d'),_text_source('server_schemas.text_be1600b499c6')) and self.end_date!=self.date:
                raise ValueError(_text_source('server_schemas.text_abe35922b3e1'))
        else:
            span = finish - begin if finish > begin else finish + 1440 - begin
        if self.kind == _text_source('server_schemas.text_bfe022ddd1f8'):
            if begin < 480 or finish > 1200 or finish <= begin or span > 480:
                raise ValueError(_text_source('server_schemas.text_47bc9db0ded4'))
        elif self.kind in (_text_source('server_schemas.text_a88b0d6dfef3'),_text_source('server_schemas.text_98a9c4972272')) and span > 480:
            raise ValueError(_text_source('server_schemas.text_0091b51ccc5f'))
        if self.kind in (_text_source('server_schemas.text_bfe022ddd1f8'), _text_source('server_schemas.text_a88b0d6dfef3')):
            if self.pause >= span or self.guest > span:
                raise ValueError(_text_source('server_schemas.text_be06a5487ee0'))
            if self.note:
                raise ValueError(_text_source('server_schemas.text_a0e9e3f1a79c'))
            if self.away and (not self.accommodation or (self.accommodation == _text_source('server_schemas.text_509b3c4e5dad') and not self.hotel_name.strip())):
                raise ValueError(_text_source('server_schemas.text_960c0e668795'))
            if not self.away and (self.accommodation or self.hotel_name):
                raise ValueError(_text_source('server_schemas.text_44a62e41a3db'))
        elif self.away or self.accommodation or self.hotel_name:
            raise ValueError(_text_source('server_schemas.text_7ff539a59c19'))
        elif self.pause >= span or self.guest > span:
            raise ValueError(_text_source('server_schemas.text_be06a5487ee0'))
        return self


class EntryBatch(BaseModel):
    entries: list[EntryIn] = Field(max_length=500)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [entry.client_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError(_text_source('server_schemas.text_25c938203a5d'))
        return self


class TfProfileUpdate(TfDetails):
    username: str | None = Field(default=None, pattern=r"^[1-9][0-9]{5}$", coerce_numbers_to_str=True)
    driver_type: Literal["route","border","both"] | None = None
    last_name: str = Field(min_length=1,max_length=120)
    first_name: str = Field(min_length=1,max_length=120)
    personnel_number: str = Field(min_length=1,max_length=40)
    target_hours_minutes: int = Field(default=0,ge=0,le=744*60)
    vacation_days: int = Field(ge=0,le=366)
    birth_date: date
    bahncard: Literal[0,50,100]
    bahncard_valid_until: date | None = None
    email: EmailStr
    federal_state: FederalState = "BE"
    photo_base64: str | None = Field(default=None,max_length=6990510)
