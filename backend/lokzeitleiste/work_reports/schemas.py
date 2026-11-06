from ..localization import source as _text_source
from datetime import datetime,time
from typing import Literal,ClassVar
from uuid import UUID
from pydantic import BaseModel,Field,field_validator,model_validator


def minutes(start,end):return int((end-start).total_seconds()//60)


def minimum_pause(duration):
    return 45+max(0,duration-600) if duration>=540 else 30 if duration>360 else 0


def required_pause(duration):return min(45,minimum_pause(duration))


def check_time(value):
    if value.tzinfo is not None or value.second or value.microsecond or not 2000<=value.year<=2100:
        raise ValueError(_text_source('server_work_reports_schemas.text_fd5142042cb8'))
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
    self_payer:bool=False

    _times=field_validator('start_at','end_at')(check_time)

    @field_validator('start_station','end_station')
    @classmethod
    def station(cls,value):
        value=value.strip().upper()
        if not value:raise ValueError(_text_source('server_work_reports_schemas.text_8c8b67c386de'))
        return value

    @model_validator(mode='after')
    def validate_trip(self):
        if self.end_at<=self.start_at:raise ValueError(_text_source('server_work_reports_schemas.text_e5bcd444576f'))
        self.transport_detail=self.transport_detail.strip() if self.transport=='other' else ''
        if self.transport=='other' and not self.transport_detail:raise ValueError(_text_source('server_work_reports_schemas.text_90ea9c46ac6c'))
        return self


REASONS=('V1','V3','A1','A1A','A3',_text_source('server_work_reports_schemas.text_858e4ba7a29f'),_text_source('server_work_reports_schemas.text_f833868f87d4'),_text_source('server_work_reports_schemas.text_1ec195f5b2d6'),'BrP','vBrP',_text_source('server_work_reports_schemas.text_64f45b98b2db'),_text_source('server_work_reports_schemas.text_cde67dfbede8'),_text_source('server_work_reports_schemas.text_979811cf207a'),_text_source('server_work_reports_schemas.text_ec85a036c547'),_text_source('server_work_reports_schemas.text_66775ecb98fd'),_text_source('server_work_reports_schemas.text_69384a6be550'))
CAUSES=('CTL',_text_source('server_work_reports_schemas.text_2087c99eb939'),_text_source('server_work_reports_schemas.text_ddadc86bec1e'),_text_source('server_work_reports_schemas.text_1abed57a73e2'),_text_source('server_work_reports_schemas.text_7fe3366aac3e'),_text_source('server_work_reports_schemas.text_69384a6be550'))


class TrainEventIn(BaseModel):
    id:UUID
    gps_stop_key:str=Field(default='',max_length=64)
    reason:str=Field(min_length=1,max_length=64)
    reason_label:str=Field(default='',max_length=200)
    reason_detail:str=Field(default='',max_length=256)
    cause:str=Field(min_length=1,max_length=64)
    cause_label:str=Field(default='',max_length=200)
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
        self.station_name=self.station_name.strip()
        if not self.station and not self.station_name and not (self.reason==_text_source('server_work_reports_schemas.text_858e4ba7a29f') and self.cause in ('CTL',_text_source('server_work_reports_schemas.text_2087c99eb939'))):raise ValueError(_text_source('server_work_reports_schemas.text_8c8b67c386de'))
        if self.end_at<=self.start_at:raise ValueError(_text_source('server_work_reports_schemas.text_7191a2755c05'))
        self.reason_detail=self.reason_detail.strip() if self.reason==_text_source('server_work_reports_schemas.text_69384a6be550') else ''
        self.cause_detail=self.cause_detail.strip() if self.cause==_text_source('server_work_reports_schemas.text_69384a6be550') else ''
        if self.reason==_text_source('server_work_reports_schemas.text_69384a6be550') and not self.reason_detail:raise ValueError(_text_source('server_work_reports_schemas.text_a68a4fbcce44'))
        if self.cause==_text_source('server_work_reports_schemas.text_69384a6be550') and not self.cause_detail:raise ValueError(_text_source('server_work_reports_schemas.text_a28beefb9700'))
        return self


class TrainJourneyIn(BaseModel):
    id:UUID
    train_number:str=Field(min_length=1,max_length=12)
    start_station:str=Field(max_length=10)
    start_station_name:str=Field(default='',max_length=255)
    end_station:str=Field(max_length=10)
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
        if not value.isalnum():raise ValueError(_text_source('server_work_reports_schemas.text_3dfbe9701ed4'))
        return value

    @model_validator(mode='after')
    def valid_journey(self):
        self.start_station_name=self.start_station_name.strip()
        self.end_station_name=self.end_station_name.strip()
        if not (self.start_station or self.start_station_name) or not (self.end_station or self.end_station_name):
            raise ValueError(_text_source('server_work_reports_schemas.text_8c8b67c386de'))
        if self.end_at<=self.start_at:raise ValueError(_text_source('server_work_reports_schemas.text_ecd10b0d9952'))
        if len({e.id for e in self.events})!=len(self.events):raise ValueError(_text_source('server_work_reports_schemas.text_e8489536b599'))
        self.events.sort(key=lambda e:(e.start_at,e.end_at,str(e.id)))
        return self


def sort_train_events(journeys):
    """Chronological views for historical JSON payloads without rewriting saved reports."""
    for journey in journeys:
        journey['events']=sorted(journey.get('events',[]),key=lambda e:(datetime.fromisoformat(e['start_at']),datetime.fromisoformat(e['end_at']),str(e.get('id',''))))
    return journeys


def train_pause_minutes(journeys):
    total=0
    for journey in journeys:
        for event in journey.get('events',[]):
            if event['reason']==_text_source('server_work_reports_schemas.text_858e4ba7a29f'):total+=minutes(datetime.fromisoformat(event['start_at']),datetime.fromisoformat(event['end_at']))
    return total


class TrainJourneysUpdate(BaseModel):
    expected_revision:int=Field(ge=0)
    train_journeys:list[TrainJourneyIn]=Field(default_factory=list,max_length=50)


class ReportIn(BaseModel):
    check_required_pause:ClassVar[bool]=True
    kind:Literal['Sonstige Erfassung','Bereitschaft','Rufbereitschaft','Ausfallschicht','Urlaub','Krank']=_text_source('server_work_reports_schemas.text_f31b8681bfca')
    client_id:UUID
    start_at:datetime
    end_at:datetime
    ausbleibe:list[Literal["8h","24h","8'h","24'h"]]=Field(default_factory=list,max_length=4)
    in_hotel:bool=False
    hotel_location:str=Field(default='',max_length=270)
    hotel_name:str=Field(default='',max_length=200)
    pause_policy:Literal[1,2]=1
    actual_pause:int=Field(default=0,ge=0,le=1440)
    overrun_reason:str=Field(default='',max_length=1000)
    trips:list[GuestIn]=Field(default_factory=list,max_length=50)
    train_journeys:list[TrainJourneyIn]=Field(default_factory=list,max_length=50)

    _times=field_validator('start_at','end_at')(check_time)

    @model_validator(mode='after')
    def validate_report(self):
        self.hotel_location=self.hotel_location.strip() if self.in_hotel else ''
        self.hotel_name=self.hotel_name.strip() if self.in_hotel else ''
        self.ausbleibe=list(dict.fromkeys(self.ausbleibe))
        duration=minutes(self.start_at,self.end_at)
        if duration<=0:raise ValueError(_text_source('server_work_reports_schemas.text_007ef8d9ea4c'))
        if self.kind in (_text_source('server_work_reports_schemas.text_a88b0d6dfef3'),_text_source('server_work_reports_schemas.text_bfe022ddd1f8'),_text_source('server_work_reports_schemas.text_98a9c4972272')) and duration>480:
            raise ValueError(_text_source('server_work_reports_schemas.text_2750690bb87f'))
        if self.kind==_text_source('server_work_reports_schemas.text_bfe022ddd1f8') and (self.start_at.date()!=self.end_at.date() or self.start_at.time()<time(8) or self.end_at.time()>time(20)):
            raise ValueError(_text_source('server_work_reports_schemas.text_a5efe0ebd18c'))
        if self.kind in (_text_source('server_work_reports_schemas.text_35d3a889824d'),_text_source('server_work_reports_schemas.text_be1600b499c6')):
            if self.start_at.date()!=self.end_at.date():raise ValueError(_text_source('server_work_reports_schemas.text_0f4caa8b3d88'))
            if self.trips or self.train_journeys or self.actual_pause:raise ValueError(_text_source('server_work_reports_schemas.text_9343742f0ae9'))
        self.overrun_reason=self.overrun_reason.strip() if self.kind==_text_source('server_work_reports_schemas.text_f31b8681bfca') else ''
        if self.kind==_text_source('server_work_reports_schemas.text_f31b8681bfca') and duration>720 and not self.overrun_reason:raise ValueError(_text_source('server_work_reports_schemas.text_fbf65bce40e9'))
        if self.actual_pause>=duration:raise ValueError(_text_source('server_work_reports_schemas.text_76b44ca0ac05'))
        ordered=sorted(self.trips,key=lambda t:t.start_at)
        for index,trip in enumerate(ordered):
            if index and trip.start_at<ordered[index-1].end_at:raise ValueError(_text_source('server_work_reports_schemas.text_05a1d9bb8fbb'))
        if sum(max(0,minutes(max(t.start_at,self.start_at),min(t.end_at,self.end_at))) for t in self.trips)>duration:
            raise ValueError(_text_source('server_work_reports_schemas.text_fb85bcca6a2b'))
        self.trips=ordered
        if len({t.id for t in self.train_journeys})!=len(self.train_journeys):raise ValueError(_text_source('server_work_reports_schemas.text_bd3d01392d89'))
        event_ids=set();pauses=[]
        for train in self.train_journeys:
            if train.start_at<self.start_at or train.end_at>self.end_at:raise ValueError(_text_source('server_work_reports_schemas.text_7f776149fd52'))
            for event in train.events:
                if event.id in event_ids:raise ValueError(_text_source('server_work_reports_schemas.text_e8489536b599'))
                event_ids.add(event.id)
                if event.start_at<self.start_at or event.end_at>self.end_at:raise ValueError(_text_source('server_work_reports_schemas.text_daa968801d2d'))
                if event.reason==_text_source('server_work_reports_schemas.text_858e4ba7a29f'):pauses.append((event.start_at,event.end_at))
        pauses.sort()
        if any(pauses[i][0]<pauses[i-1][1] for i in range(1,len(pauses))):raise ValueError(_text_source('server_work_reports_schemas.text_5f35fa8f3600'))
        if self.actual_pause+sum(minutes(a,b) for a,b in pauses)>duration:raise ValueError(_text_source('server_work_reports_schemas.text_c00121dc0425'))
        if self.check_required_pause and self.pause_policy==2 and self.kind==_text_source('server_work_reports_schemas.text_f31b8681bfca') and self.actual_pause+sum(minutes(a,b) for a,b in pauses)<required_pause(duration):raise ValueError(_text_source('server_work_reports_schemas.text_3eb7d4c1515c')+str(required_pause(duration))+_text_source('server_work_reports_schemas.text_54542d79a9f0'))
        return self


class DraftReportIn(ReportIn):
    # Only the draft endpoint relaxes minimum-pause completion. Final reports
    # always use ReportIn; clients cannot disable this check through payloads.
    check_required_pause:ClassVar[bool]=False
