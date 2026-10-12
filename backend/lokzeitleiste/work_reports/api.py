from fastapi import APIRouter,BackgroundTasks,Depends,HTTPException,UploadFile,File,Query
from fastapi.responses import Response,FileResponse
from pathlib import Path
from sqlalchemy import select,func
import calendar
from datetime import date,datetime,time,timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from ..db import database_session
from ..models import User,DutyReport,DutyReceipt,RailwayStation,TfProfile
from ..tf_portal import driver_dependency
from ..records.service import assert_unlocked
from .schemas import ReportIn
from .service import save_report,report_view
from .receipts import MAX_FILE,validate_receipt,recipient,receipt_view,process_receipt


def create_router(require_account):
    router=APIRouter()
    driver=driver_dependency(require_account)

    def owned(db,user,report_id,lock=False):
        query=select(DutyReport).where(DutyReport.id==report_id,DutyReport.tf_user_id==user.id)
        report=db.scalar(query.with_for_update() if lock else query)
        if not report:raise HTTPException(404,'Arbeitsbericht nicht gefunden.')
        return report

    @router.get('/tf/work-report.js')
    def script():return FileResponse(Path(__file__).parent.parent/'static'/'work-report.js',media_type='text/javascript')

    @router.get('/tf/work-report.css')
    def styles():return FileResponse(Path(__file__).parent.parent/'static'/'work-report.css',media_type='text/css')

    @router.get('/api/v1/tf/work-reports/stations')
    def stations(q:str=Query(min_length=1,max_length=80),user:User=Depends(driver),db:Session=Depends(database_session)):
        text=q.strip().upper().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        rows=db.scalars(select(RailwayStation).where(
            RailwayStation.code.ilike(text+'%',escape='\\')).order_by(RailwayStation.code).limit(20)).all()
        return [{'code':r.code,'name':r.name} for r in rows]

    @router.post('/api/v1/tf/work-reports',status_code=201)
    def create(data:ReportIn,user:User=Depends(driver),db:Session=Depends(database_session)):
        return report_view(db,save_report(db,user,data))

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
                work_minutes=sum(r.work for r in rows),guest_minutes=sum(r.guest for r in rows),pause_minutes=sum(r.pause for r in rows)))
        reports=db.scalars(select(DutyReport).where(DutyReport.tf_user_id==user.id,DutyReport.entry_id.in_([e.id for e in entries])).order_by(DutyReport.id.desc())).all()
        return dict(days=days,work_minutes=sum(d['work_minutes'] for d in days),guest_minutes=sum(d['guest_minutes'] for d in days),pause_minutes=sum(d['pause_minutes'] for d in days),
                    reports=[report_view(db,r) for r in reports])

    @router.get('/api/v1/tf/work-reports/{report_id}')
    def read_report(report_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        return report_view(db,owned(db,user,report_id))

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
