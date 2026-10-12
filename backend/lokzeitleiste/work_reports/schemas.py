from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,Field,field_validator,model_validator


def minutes(start,end):return int((end-start).total_seconds()//60)


def minimum_pause(duration):
    return 45+duration-600 if duration>600 else 45 if duration>540 else 30 if duration>360 else 0


def check_time(value):
    if value.tzinfo is not None or value.second or value.microsecond or not 2000<=value.year<=2100:
        raise ValueError('Datum und Uhrzeit müssen minutengenau und ohne Zeitzonenangabe sein (2000–2100).')
    return value


class GuestIn(BaseModel):
    start_station:str=Field(min_length=1,max_length=10)
    end_station:str=Field(min_length=1,max_length=10)
    start_station_name:str=Field(default='',max_length=255)
    end_station_name:str=Field(default='',max_length=255)
    start_at:datetime
    end_at:datetime
    transport:Literal['train','car','taxi','public_transport','other']
    transport_detail:str=Field(default='',max_length=140)

    _times=field_validator('start_at','end_at')(check_time)

    @field_validator('start_station','end_station')
    @classmethod
    def station(cls,value):
        value=value.strip().upper()
        if not value:raise ValueError('DS100-Kürzel erforderlich.')
        return value

    @model_validator(mode='after')
    def validate_trip(self):
        if self.end_at<=self.start_at:raise ValueError('Gastfahrtende muss nach dem Beginn liegen.')
        self.transport_detail=self.transport_detail.strip() if self.transport=='other' else ''
        if self.transport=='other' and not self.transport_detail:raise ValueError('Anderes Transportmittel bitte beschreiben.')
        return self


class ReportIn(BaseModel):
    client_id:UUID
    start_at:datetime
    end_at:datetime
    actual_pause:int=Field(default=0,ge=0,le=1440)
    overrun_reason:str=Field(default='',max_length=1000)
    trips:list[GuestIn]=Field(default_factory=list,max_length=50)

    _times=field_validator('start_at','end_at')(check_time)

    @model_validator(mode='after')
    def validate_report(self):
        duration=minutes(self.start_at,self.end_at)
        if duration<=0:raise ValueError('Dienstende muss nach Dienstbeginn liegen.')
        self.overrun_reason=self.overrun_reason.strip()
        if duration>720 and not self.overrun_reason:raise ValueError('Bei mehr als zwölf Stunden ist eine Begründung erforderlich.')
        if self.actual_pause>=duration:raise ValueError('Die tatsächliche Pause muss kürzer als der Dienst sein.')
        ordered=sorted(self.trips,key=lambda t:t.start_at)
        for index,trip in enumerate(ordered):
            if index and trip.start_at<ordered[index-1].end_at:raise ValueError('Gastfahrten dürfen sich nicht überschneiden.')
        if sum(max(0,minutes(max(t.start_at,self.start_at),min(t.end_at,self.end_at))) for t in self.trips)>duration-self.actual_pause:
            raise ValueError('Gastfahrtzeit und tatsächliche Pause überschreiten die Dienstzeit.')
        self.trips=ordered
        return self
