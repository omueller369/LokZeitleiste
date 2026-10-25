from fastapi import APIRouter,BackgroundTasks,Depends,HTTPException,UploadFile,File,Query,Header
from fastapi.responses import Response,FileResponse
from pathlib import Path
from sqlalchemy import select,func,or_,case
import calendar
from datetime import date,datetime,time,timedelta
from collections import defaultdict,Counter
import json
from sqlalchemy.orm import Session
from ..db import database_session
from ..models import User,DutyReport,DutyGuestTrip,DutyReceipt,RailwayStation,TfProfile
from ..tf_portal import driver_dependency
from ..records.service import assert_unlocked
from .schemas import ReportIn,TrainJourneysUpdate
from .service import save_report,report_view,update_train_journeys
from ..reports.absence import absence_minutes
from .receipts import MAX_FILE,validate_receipt,recipient,receipt_view,process_receipt


def create_router(require_account):
    router=APIRouter()
    driver=driver_dependency(require_account)

    def owned(db,user,report_id,lock=False):
        query=select(DutyReport).where(DutyReport.id==report_id,DutyReport.tf_user_id==user.id)
        report=db.scalar(query.with_for_update() if lock else query)
        if not report:raise HTTPException(404,'Arbeitsbericht nicht gefunden.')
        return report

    @router.get('/tf/work-report-feedback.js')
    def feedback_script():return FileResponse(Path(__file__).parent.parent/'static'/'work-report-feedback.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})

    @router.get('/tf/work-report.js')
    def script():return FileResponse(Path(__file__).parent.parent/'static'/'work-report.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})

    @router.get('/tf/train-journeys.js')
    def train_script():return FileResponse(Path(__file__).parent.parent/'static'/'train-journeys.js',media_type='text/javascript')

    @router.get('/tf/work-report.css')
    def styles():return FileResponse(Path(__file__).parent.parent/'static'/'work-report.css',media_type='text/css')

    @router.get('/api/v1/tf/work-reports/stations')
    def stations(q:str=Query(min_length=1,max_length=255),user:User=Depends(driver),db:Session=Depends(database_session)):
        text=q.strip().upper().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        rows=db.scalars(select(RailwayStation).where(
            or_(RailwayStation.code.ilike(text+'%',escape='\\'),RailwayStation.name.ilike('%'+text+'%',escape='\\'))).order_by(case((RailwayStation.code==q.strip().upper(),0),(RailwayStation.code.ilike(text+'%',escape='\\'),1),else_=2),RailwayStation.code).limit(20)).all()
        return [{'code':r.code,'name':r.name} for r in rows]

    @router.get('/api/v1/tf/work-reports/stations/frequent')
    def frequent_stations(user:User=Depends(driver),db:Session=Depends(database_session)):
        counts=Counter()
        # Count current saved reports, never retry submissions or another TF's data.
        for raw in db.scalars(select(DutyReport.payload_json).where(DutyReport.tf_user_id==user.id)):
            payload=json.loads(raw)
            for trip in payload.get('trips',[])+payload.get('train_journeys',[]):
                for key in ('start_station','end_station'):
                    code=trip.get(key,'').strip().upper()
                    if code:counts[code]+=1
            for train in payload.get('train_journeys',[]):
                for event in train.get('events',[]):
                    code=event.get('station','').strip().upper()
                    if code:counts[code]+=1
        if not counts:return []
        # Resolve against today's catalogue so obsolete codes are not suggested.
        ordered=sorted(counts,key=lambda code:(-counts[code],code));result=[]
        for offset in range(0,len(ordered),200):
            codes=ordered[offset:offset+200]
            catalogue={row.code:row.name for row in db.scalars(select(RailwayStation).where(RailwayStation.code.in_(codes)))}
            for code in codes:
                if code in catalogue:result.append(dict(code=code,name=catalogue[code],count=counts[code]))
                if len(result)==6:return result
        return result

    @router.post('/api/v1/tf/work-reports',status_code=201)
    def create(data:ReportIn,tasks:BackgroundTasks,draft_revision:int|None=Header(default=None,alias='X-CTL-Draft-Revision'),user:User=Depends(driver),db:Session=Depends(database_session)):
        from .drafts import before_finalize,finalize_files
        draft=before_finalize(db,user,data.client_id,draft_revision)
        report=save_report(db,user,data,commit=False)
        receipt_ids=finalize_files(db,draft,report)
        db.commit()
        for receipt_id in receipt_ids:tasks.add_task(process_receipt,receipt_id)
        return report_view(db,report)

    @router.get('/api/v1/tf/work-reports/month/{year}/{month}')
    def month_view(year:int,month:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        if not 2000<=year<=2100 or not 1<=month<=12:raise HTTPException(422,'Ungültiger Monat')
        from ..reports.intervals import period_entries
        from ..reports.daily import day_rows,WORK_KINDS
        first=date(year,month,1);last=date(year,month,calendar.monthrange(year,month)[1])
        entries=period_entries(db,user.id,first,last)
        profile=db.get(TfProfile,user.id)
        if not profile:raise HTTPException(404,'Tf nicht gefunden')
        grouped=defaultdict(list)
        for row in day_rows(entries,profile.federal_state or 'BE'):
            if first<=row.day<=last and row.kind in WORK_KINDS:grouped[row.day].append(row)
        days=[]
        for day,rows in sorted(grouped.items()):
            end=max(datetime.combine(day+timedelta(days=1) if r.end==time.min else day,r.end) for r in rows)
            days.append(dict(date=day.isoformat(),start_at=datetime.combine(day,min(r.start for r in rows)).isoformat(),end_at=end.isoformat(),
                performed_minutes=sum(r.work for r in rows),work_minutes=sum(r.work for r in rows),guest_minutes=sum(r.guest for r in rows),pause_minutes=sum(r.pause for r in rows)))
        by_date={d['date']:d for d in days}
        for entry in entries:
            if entry.kind in ('Urlaub','Krank') and first<=entry.entry_date<=last:
                day=entry.entry_date.isoformat()
                if day not in by_date:
                    row=dict(date=day,start_at=None,end_at=None,performed_minutes=0,work_minutes=absence_minutes(entry),guest_minutes=0,pause_minutes=0);days.append(row);by_date[day]=row
        period_start=datetime.combine(first,time.min);period_end=datetime.combine(last+timedelta(days=1),time.min)
        guest_report_ids=select(DutyGuestTrip.report_id).where(DutyGuestTrip.start_at<period_end,DutyGuestTrip.end_at>period_start)
        reports=db.scalars(select(DutyReport).where(DutyReport.tf_user_id==user.id,or_(DutyReport.entry_id.in_([e.id for e in entries]),DutyReport.id.in_(guest_report_ids))).order_by(DutyReport.id.desc())).all()
        external=defaultdict(int)
        views=[report_view(db,r) for r in reports]
        for view in views:
            start=datetime.fromisoformat(view['start_at']);end=datetime.fromisoformat(view['end_at'])
            for trip in view['trips']:
                a=datetime.fromisoformat(trip['start_at']);b=datetime.fromisoformat(trip['end_at'])
                for lo,hi in ((a,min(b,start)),(max(a,end),b)):
                    lo=max(lo,period_start);hi=min(hi,period_end)
                    while lo<hi:
                        boundary=min(hi,datetime.combine(lo.date()+timedelta(days=1),time.min))
                        external[lo.date().isoformat()]+=int((boundary-lo).total_seconds()//60);lo=boundary
        by_date={d['date']:d for d in days}
        for day,total in external.items():
            if day not in by_date:
                row=dict(date=day,start_at=None,end_at=None,performed_minutes=0,work_minutes=0,guest_minutes=0,pause_minutes=0);days.append(row);by_date[day]=row
        for row in days:row['external_guest_minutes']=external[row['date']]
        days.sort(key=lambda d:d['date'])
        return dict(days=days,work_minutes=sum(d['work_minutes'] for d in days),guest_minutes=sum(d['guest_minutes'] for d in days),pause_minutes=sum(d['pause_minutes'] for d in days),
                    external_guest_minutes=sum(external.values()),reports=views)

    @router.get('/api/v1/tf/work-reports/{report_id}')
    def read_report(report_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        return report_view(db,owned(db,user,report_id))

    @router.put('/api/v1/tf/work-reports/{report_id}/train-journeys')
    def change_trains(report_id:int,data:TrainJourneysUpdate,user:User=Depends(driver),db:Session=Depends(database_session)):
        from pydantic import ValidationError
        try:return report_view(db,update_train_journeys(db,user,owned(db,user,report_id,lock=True),data))
        except ValidationError as exc:raise HTTPException(422,str(exc.errors()[0]['msg'])) from exc

    @router.get('/api/v1/tf/work-reports/{report_id}/receipts')
    def receipts(report_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        owned(db,user,report_id)
        return [receipt_view(row) for row in db.scalars(select(DutyReceipt).where(DutyReceipt.report_id==report_id).order_by(DutyReceipt.id))]

    @router.post('/api/v1/tf/work-reports/{report_id}/receipts',status_code=202)
    async def upload(report_id:int,tasks:BackgroundTasks,file:UploadFile=File(...),user:User=Depends(driver),db:Session=Depends(database_session)):
        try:content=await file.read(MAX_FILE+1)
        finally:await file.close()
        try:name,mime,digest=validate_receipt(file.filename,content)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        report=owned(db,user,report_id,lock=True)
        assert_unlocked(db,report.entry_id)
        row=db.scalar(select(DutyReceipt).where(DutyReceipt.report_id==report_id,DutyReceipt.content_hash==digest))
        if not row:
            count=db.scalar(select(func.count()).select_from(DutyReceipt).where(DutyReceipt.report_id==report_id))
            if count>=20:raise HTTPException(422,'Höchstens 20 Belege pro Arbeitsbericht.')
            row=DutyReceipt(report_id=report_id,filename=name,mime_type=mime,content_hash=digest,content=content,recipient_email=recipient())
            db.add(row);db.commit();db.refresh(row)
        if row.status!='sent':tasks.add_task(process_receipt,row.id)
        return receipt_view(row)

    @router.get('/api/v1/tf/work-reports/{report_id}/receipts/{receipt_id}')
    def download(report_id:int,receipt_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        owned(db,user,report_id)
        row=db.get(DutyReceipt,receipt_id)
        if not row or row.report_id!=report_id:raise HTTPException(404,'Beleg nicht gefunden.')
        return Response(row.content,media_type=row.mime_type,headers={'Content-Disposition':f'attachment; filename="Beleg-{row.id}{Path(row.filename).suffix}"','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/api/v1/tf/work-reports/{report_id}/receipts/{receipt_id}/retry')
    def retry(report_id:int,receipt_id:int,tasks:BackgroundTasks,user:User=Depends(driver),db:Session=Depends(database_session)):
        owned(db,user,report_id,lock=True)
        row=db.get(DutyReceipt,receipt_id)
        if not row or row.report_id!=report_id:raise HTTPException(404,'Beleg nicht gefunden.')
        if row.status!='sent':row.status='pending';row.attempts=0;row.last_error='';db.commit();tasks.add_task(process_receipt,row.id)
        return receipt_view(row)

    return router
