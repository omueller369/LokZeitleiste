from datetime import datetime,time
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


REASONS=('V1','V3','A1','A1A','A3','Pause','Rangieren','Zugvorbereitung','BrP','vBrP','Zugfolge','Warten auf Zug','Warten auf Fpl','Warten auf FPLO','Lok defekt','sonstiges')
CAUSES=('CTL Logistics DE','CTL Logistics PL','DB InfraGo','Dritte Stelle','sonstiges')


class TrainEventIn(BaseModel):
    id:UUID
    reason:Literal['V1','V3','A1','A1A','A3','Pause','Rangieren','Zugvorbereitung','BrP','vBrP','Zugfolge','Warten auf Zug','Warten auf Fpl','Warten auf FPLO','Lok defekt','sonstiges']
    reason_detail:str=Field(default='',max_length=256)
    cause:Literal['CTL Logistics DE','CTL Logistics PL','DB InfraGo','Dritte Stelle','sonstiges']
    cause_detail:str=Field(default='',max_length=50)
    station:str=Field(default='',max_length=10)
    station_name:str=Field(default='',max_length=255)
    start_at:datetime
    end_at:datetime
    _times=field_validator('start_at','end_at')(check_time)

    @field_validator('station')
    @classmethod
    def code(cls,value):return value.strip().upper()

    @model_validator(mode='after')
    def valid_event(self):
        if not self.station and not (self.reason=='Pause' and self.cause=='CTL Logistics DE'):raise ValueError('DS100-Kürzel erforderlich.')
        if not self.station:self.station_name=''
        if self.end_at<=self.start_at:raise ValueError('Bis muss nach Von liegen.')
        self.reason_detail=self.reason_detail.strip() if self.reason=='sonstiges' else ''
        self.cause_detail=self.cause_detail.strip() if self.cause=='sonstiges' else ''
        if self.reason=='sonstiges' and not self.reason_detail:raise ValueError('Sonstigen Grund bitte beschreiben.')
        if self.cause=='sonstiges' and not self.cause_detail:raise ValueError('Sonstigen Verursacher bitte beschreiben.')
        return self


class TrainJourneyIn(BaseModel):
    id:UUID
    train_number:str=Field(min_length=1,max_length=12)
    start_station:str=Field(min_length=1,max_length=10)
    start_station_name:str=Field(default='',max_length=255)
    end_station:str=Field(min_length=1,max_length=10)
    end_station_name:str=Field(default='',max_length=255)
    start_at:datetime
    end_at:datetime
    events:list[TrainEventIn]=Field(default_factory=list,max_length=500)
    _times=field_validator('start_at','end_at')(check_time)

    @field_validator('start_station','end_station')
    @classmethod
    def code(cls,value):return value.strip().upper()

    @field_validator('train_number')
    @classmethod
    def number(cls,value):
        value=value.strip()
        if not value.isalnum():raise ValueError('Zugnummer: nur Buchstaben und Zahlen, maximal zwölf Zeichen.')
        return value

    @model_validator(mode='after')
    def valid_journey(self):
        if self.end_at<=self.start_at:raise ValueError('Ankunft muss nach Abfahrt liegen.')
        if len({e.id for e in self.events})!=len(self.events):raise ValueError('Ereignis-IDs müssen eindeutig sein.')
        return self


def train_pause_minutes(journeys):
    total=0
    for journey in journeys:
        for event in journey.get('events',[]):
            if event['reason']=='Pause':total+=minutes(datetime.fromisoformat(event['start_at']),datetime.fromisoformat(event['end_at']))
    return total


class TrainJourneysUpdate(BaseModel):
    expected_revision:int=Field(ge=0)
    train_journeys:list[TrainJourneyIn]=Field(default_factory=list,max_length=50)


class ReportIn(BaseModel):
    kind:Literal['Sonstige Erfassung','Bereitschaft','Rufbereitschaft','Ausfallschicht','Urlaub','Krank']='Sonstige Erfassung'
    client_id:UUID
    start_at:datetime
    end_at:datetime
    ausbleibe:list[Literal["8h","24h","8'h","24'h"]]=Field(default_factory=list,max_length=4)
    actual_pause:int=Field(default=0,ge=0,le=1440)
    overrun_reason:str=Field(default='',max_length=1000)
    trips:list[GuestIn]=Field(default_factory=list,max_length=50)
    train_journeys:list[TrainJourneyIn]=Field(default_factory=list,max_length=50)

    _times=field_validator('start_at','end_at')(check_time)

    @model_validator(mode='after')
    def validate_report(self):
        self.ausbleibe=list(dict.fromkeys(self.ausbleibe))
        duration=minutes(self.start_at,self.end_at)
        if duration<=0:raise ValueError('Dienstende muss nach Dienstbeginn liegen.')
        if self.kind in ('Bereitschaft','Rufbereitschaft','Ausfallschicht') and duration>480:
            raise ValueError('Diese Dienstart darf höchstens acht Stunden dauern.')
        if self.kind=='Rufbereitschaft' and (self.start_at.date()!=self.end_at.date() or self.start_at.time()<time(8) or self.end_at.time()>time(20)):
            raise ValueError('Rufbereitschaft ist nur zwischen 08:00 und 20:00 Uhr am selben Tag zulässig.')
        if self.kind in ('Urlaub','Krank'):
            if self.start_at.date()!=self.end_at.date():raise ValueError('Urlaub und Krank werden je Tag einzeln erfasst.')
            if self.trips or self.train_journeys or self.actual_pause:raise ValueError('Urlaub und Krank enthalten keine Gastfahrten oder Pausen.')
        self.overrun_reason=self.overrun_reason.strip() if self.kind=='Sonstige Erfassung' else ''
        if self.kind=='Sonstige Erfassung' and duration>720 and not self.overrun_reason:raise ValueError('Bei mehr als zwölf Stunden ist eine Begründung erforderlich.')
        if self.actual_pause>=duration:raise ValueError('Die tatsächliche Pause muss kürzer als der Dienst sein.')
        ordered=sorted(self.trips,key=lambda t:t.start_at)
        for index,trip in enumerate(ordered):
            if index and trip.start_at<ordered[index-1].end_at:raise ValueError('Gastfahrten dürfen sich nicht überschneiden.')
        if sum(max(0,minutes(max(t.start_at,self.start_at),min(t.end_at,self.end_at))) for t in self.trips)>duration:
            raise ValueError('Gastfahrtzeit im Dienst überschreitet die Dienstzeit.')
        self.trips=ordered
        if len({t.id for t in self.train_journeys})!=len(self.train_journeys):raise ValueError('Zugfahrt-IDs müssen eindeutig sein.')
        event_ids=set();pauses=[]
        for train in self.train_journeys:
            if train.start_at<self.start_at or train.end_at>self.end_at:raise ValueError('Zugfahrten müssen innerhalb des Dienstes liegen.')
            for event in train.events:
                if event.id in event_ids:raise ValueError('Ereignis-IDs müssen eindeutig sein.')
                event_ids.add(event.id)
                if event.start_at<self.start_at or event.end_at>self.end_at:raise ValueError('Zugfahrtereignisse müssen innerhalb des Dienstes liegen.')
                if event.reason=='Pause':pauses.append((event.start_at,event.end_at))
        pauses.sort()
        if any(pauses[i][0]<pauses[i-1][1] for i in range(1,len(pauses))):raise ValueError('Dokumentierte Pausen dürfen sich nicht überschneiden.')
        if self.actual_pause+sum(minutes(a,b) for a,b in pauses)>duration:raise ValueError('Dokumentierte Pausen überschreiten die Dienstzeit.')
        return self
