import os
from pathlib import Path

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from .db import database_session
from .models import ReportDispatch, TfProfile, User, WorkEntry, WorkMonth, WorkTimeChange, AccountPolicy, WorkEntryLock, ProfilePhoto, now_utc
from .schemas import TfProfileUpdate, EntryIn, Credentials, EntryBatch, TfCreate, TfDeliveryUpdate
from .security import issue_token, revoke_token, user_from_token, verify_password, hash_password
from .reports.daily import day_rows
from .reports.mailer import smtp_configured
from .reports.pdf import render_receipt_pdf
from .reports.monthly import summarize_month
from .reports.service import process_dispatch
from .accounts.access import authorize_route, password_required, ready, permissions, redact_plan


app = FastAPI(title="LokZeitleiste API", version="0.16")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
PUBLIC_ORIGIN = os.getenv("PUBLIC_ORIGIN", "")


def require_tf(request: Request, authorization: str | None = Header(default=None), db: Session = Depends(database_session)) -> User:
    token = authorization.removeprefix("Bearer ").strip() if authorization and authorization.startswith("Bearer ") else ""
    user = user_from_token(db, token)
    if not user or user.role != "tf":
        raise HTTPException(401, "Tf-Anmeldung erforderlich")
    if request.url.path != '/api/v1/tf/logout':
        ready(db,user)
    return user


def require_admin(request: Request, admin_session: str | None = Cookie(default=None),
                  db: Session = Depends(database_session)) -> User:
    user = user_from_token(db, admin_session)
    if not user or user.role not in ("admin", "staff"):
        raise HTTPException(401, "Admin-Anmeldung erforderlich")
    if request.method not in ("GET", "HEAD") and PUBLIC_ORIGIN and request.headers.get("origin") != PUBLIC_ORIGIN:
        raise HTTPException(403, "Ungültiger Ursprung")
    authorize_route(db,user,request)
    return user


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/admin")
def admin_page():
    return FileResponse(Path(__file__).parent / "static" / "admin.html")


@app.get("/admin/admin.js")
def admin_script():
    return FileResponse(Path(__file__).parent / "static" / "admin.js", media_type="text/javascript")


@app.post("/api/v1/admin/login")
def admin_login(credentials: Credentials, request: Request, response: Response, db: Session = Depends(database_session)):
    if PUBLIC_ORIGIN and request.headers.get('origin') != PUBLIC_ORIGIN:
        raise HTTPException(403, "Ungültiger Ursprung")
    user = db.scalar(select(User).where(User.username == credentials.username.lower(), User.role.in_(("admin", "staff"))))
    if not user or not user.active or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(401, "Anmeldung fehlgeschlagen")
    token = issue_token(db, user)
    response.set_cookie("admin_session", token, httponly=True, secure=COOKIE_SECURE,
                        samesite="strict", max_age=365 * 24 * 3600, path="/")
    return {"username": user.username, "role":user.role, "password_change_required":password_required(db,user)}


@app.post("/api/v1/admin/logout")
def admin_logout(response: Response, admin_session: str | None = Cookie(default=None),
                 _: User = Depends(require_admin), db: Session = Depends(database_session)):
    if admin_session:
        revoke_token(db, admin_session)
    response.delete_cookie("admin_session", path="/")
    return {"ok": True}


@app.post("/api/v1/admin/tf", status_code=201)
def create_tf(data: TfCreate, _: User = Depends(require_admin), db: Session = Depends(database_session)):
    from .accounts.photos import decode_photo,save_photo
    image=decode_photo(data.photo_base64)
    username = data.username.strip().lower()
    if not username or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for c in username):
        raise HTTPException(422, "Ungültiger Benutzername")
    try:
        user = User(username=username, password_hash=hash_password(data.password), role="tf")
        db.add(user)
        db.flush()
        db.add(AccountPolicy(user_id=user.id,must_change_password=True))
        db.add(TfProfile(user_id=user.id, last_name=data.last_name.strip(), first_name=data.first_name.strip(),
                         personnel_number=data.personnel_number.strip(),
                         target_hours_minutes=data.target_hours_minutes,
                         vacation_days=data.vacation_days, birth_date=data.birth_date, bahncard=data.bahncard,
                         email=str(data.email), federal_state=data.federal_state))
        save_photo(db,user.id,image)
        db.commit()
        return {"id": user.id, "username": user.username}
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Benutzername oder Personalnummer bereits vorhanden")


@app.get("/api/v1/admin/tf")
def list_tf(viewer: User = Depends(require_admin), db: Session = Depends(database_session)):
    rows = db.execute(select(User, TfProfile).join(TfProfile).where(User.role == "tf").order_by(TfProfile.last_name)).all()
    if permissions(db,viewer)["employees"] == 0:
        return [{"id":u.id,"first_name":p.first_name,"last_name":p.last_name,"personnel_number":p.personnel_number} for u,p in rows]
    return [{"id": user.id, "username": user.username, "active": user.active,
             "last_name": p.last_name, "first_name": p.first_name, "personnel_number": p.personnel_number,
             "target_hours_minutes": p.target_hours_minutes, "vacation_days": p.vacation_days,
             "birth_date": p.birth_date.isoformat(), "bahncard": p.bahncard,
             "email": p.email, "federal_state": p.federal_state, "has_photo":db.get(ProfilePhoto,user.id) is not None} for user, p in rows]


@app.put("/api/v1/admin/tf/{tf_id}")
def update_tf(tf_id:int,data:TfProfileUpdate,actor:User=Depends(require_admin),db:Session=Depends(database_session)):
    from .accounts.photos import decode_photo,save_photo
    user=db.scalar(select(User).where(User.id==tf_id).with_for_update())
    profile=db.get(TfProfile,tf_id)
    if not user or user.role!='tf' or not profile:raise HTTPException(404,'Tf nicht gefunden')
    image=decode_photo(data.photo_base64)
    try:
        for field in ('last_name','first_name','personnel_number','target_hours_minutes','vacation_days','birth_date','bahncard','email','federal_state'):
            value=getattr(data,field)
            setattr(profile,field,value.strip() if isinstance(value,str) else value)
        save_photo(db,tf_id,image)
        db.commit()
        return {'id':tf_id,'has_photo':db.get(ProfilePhoto,tf_id) is not None}
    except IntegrityError as exc:
        db.rollback();raise HTTPException(409,'Personalnummer bereits vergeben') from exc


@app.patch("/api/v1/admin/tf/{tf_id}/delivery")
def update_tf_delivery(tf_id: int, data: TfDeliveryUpdate, _: User = Depends(require_admin),
                       db: Session = Depends(database_session)):
    profile = db.get(TfProfile, tf_id)
    if not profile or not db.get(User, tf_id) or db.get(User, tf_id).role != "tf":
        raise HTTPException(404, "Tf nicht gefunden")
    profile.email = str(data.email)
    profile.federal_state = data.federal_state
    db.commit()
    return {"id": tf_id, "email": profile.email, "federal_state": profile.federal_state}


@app.get("/api/v1/admin/tf/{tf_id}/reports")
def report_status(tf_id: int, _: User = Depends(require_admin), db: Session = Depends(database_session)):
    reports = db.scalars(select(ReportDispatch).where(ReportDispatch.tf_user_id == tf_id)
                         .order_by(ReportDispatch.id.desc()).limit(30)).all()
    return [{"id": item.id, "status": item.status, "recipient_email": item.recipient_email,
             "created_at": item.created_at.isoformat(), "sent_at": item.sent_at.isoformat() if item.sent_at else None,
             "attempts": item.attempts, "last_error": item.last_error} for item in reports]


@app.get("/api/v1/admin/tf/{tf_id}/months")
def list_months(tf_id: int, _: User = Depends(require_admin), db: Session = Depends(database_session)):
    user = db.get(User, tf_id)
    if not user or user.role != "tf":
        raise HTTPException(404, "Tf nicht gefunden")
    months = db.scalars(select(WorkMonth).where(WorkMonth.tf_user_id == tf_id)
                        .order_by(WorkMonth.year.desc(), WorkMonth.month.desc())).all()
    return [{"year": m.year, "month": m.month, "entry_count": len(m.entries)} for m in months]


@app.get("/api/v1/admin/tf/{tf_id}/months/{year}/{month}/entries")
def admin_entries(tf_id: int, year: int, month: int, _: User = Depends(require_admin),
                  db: Session = Depends(database_session)):
    period = db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id == tf_id,
                                              WorkMonth.year == year, WorkMonth.month == month))
    return [entry_dict(e) for e in period.entries] if period else []


def month_summary(db: Session, tf_id: int, year: int, month: int):
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        raise HTTPException(422, "Ungültiger Monat")
    profile = db.get(TfProfile, tf_id)
    if not profile or not profile.federal_state:
        raise HTTPException(409, "Bundesland des Tf fehlt im Admin-Profil")
    from .reports.intervals import period_entries
    from datetime import date
    import calendar
    entries=period_entries(db,tf_id,date(year,month,1),date(year,month,calendar.monthrange(year,month)[1]))
    try:
        result = summarize_month(entries, year=year, month=month, federal_state=profile.federal_state)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    from .planning.service import get_month
    planning = get_month(db, tf_id, year, month)
    result["planning"] = planning
    result["target_minutes"] = planning["target_minutes"]
    result["balance_minutes"] = result["totals"]["credited"] - planning["target_minutes"] if planning["complete"] else None
    result["tf_user_id"] = tf_id
    today = datetime.now(ZoneInfo("Europe/Berlin"))
    result["status"] = "vorläufig" if (year, month) >= (today.year, today.month) else "Monatsende"
    return result


@app.get("/api/v1/admin/tf/{tf_id}/months/{year}/{month}/summary")
def admin_month_summary(tf_id: int, year: int, month: int, viewer: User = Depends(require_admin),
                        db: Session = Depends(database_session)):
    user = db.get(User, tf_id)
    if not user or user.role != "tf":
        raise HTTPException(404, "Tf nicht gefunden")
    return redact_plan(db,viewer,month_summary(db, tf_id, year, month))


@app.get("/api/v1/me/months/{year}/{month}/summary")
def my_month_summary(year: int, month: int, user: User = Depends(require_tf),
                     db: Session = Depends(database_session)):
    return month_summary(db, user.id, year, month)


@app.post("/api/v1/tf/login")
def tf_login(credentials: Credentials, db: Session = Depends(database_session)):
    user = db.scalar(select(User).where(User.username == credentials.username.lower(), User.role == "tf"))
    if not user or not user.active or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(401, "Anmeldung fehlgeschlagen")
    return {"access_token": issue_token(db, user), "token_type": "bearer", "username": user.username, "password_change_required":password_required(db,user)}


@app.post("/api/v1/tf/logout")
def tf_logout(authorization: str | None = Header(default=None), _: User = Depends(require_tf),
              db: Session = Depends(database_session)):
    if authorization:
        revoke_token(db, authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


def entry_dict(e: WorkEntry):
    return {"end_date":e.explicit_end_date.isoformat() if e.explicit_end_date else None,"client_id": e.client_id, "kind": e.kind, "date": e.entry_date.isoformat(),
            "start": e.start_time, "end": e.end_time, "pause": e.pause_minutes,
            "guest": e.guest_minutes, "note": e.note, "away": e.away,
            "accommodation": e.accommodation, "hotel_name": e.hotel_name}


@app.post("/api/v1/me/months/{year}/{month}/entries")
def upload_entries(year: int, month: int, batch: EntryBatch, background_tasks: BackgroundTasks,
                   user: User = Depends(require_tf), db: Session = Depends(database_session)):
    return persist_entries(year,month,batch,background_tasks,user,db)


def persist_entries(year,month,batch,background_tasks,user,db,manual_actor=None):
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        raise HTTPException(422, "Ungültiger Monat")
    if any(e.date.year != year or e.date.month != month for e in batch.entries):
        raise HTTPException(422, "Eintrag gehört nicht zum angeforderten Monat")
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    profile = db.get(TfProfile, user.id)
    if not profile or not profile.email or not profile.federal_state:
        raise HTTPException(409, "E-Mail-Adresse und Bundesland des Tf fehlen im Admin-Profil")
    if batch.entries and not smtp_configured():
        raise HTTPException(503, "E-Mail-Versand ist auf dem Server noch nicht eingerichtet")
    period = db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id == user.id,
                                              WorkMonth.year == year, WorkMonth.month == month).with_for_update())
    if not period:
        period = WorkMonth(tf_user_id=user.id, year=year, month=month)
        db.add(period)
        db.flush()
    existing = {e.client_id: e for e in db.scalars(select(WorkEntry).where(
        WorkEntry.work_month_id == period.id).with_for_update()).all()}
    from .reports.intervals import set_end_date, touched_months, entry_end_date
    # Alte Apps ohne Enddatum dürfen ein explizit gespeichertes Enddatum nicht löschen.
    try:
        batch=EntryBatch(entries=[EntryIn.model_validate(dict(item.model_dump(),end_date=(existing[str(item.client_id)].explicit_end_date
            if item.end_date is None and str(item.client_id) in existing else item.end_date))) for item in batch.entries])
    except ValidationError as exc:
        raise HTTPException(422,'Ungültiger Zeitraum mit gespeichertem Enddatum: '+str(exc.errors()[0]['msg'])) from exc
    # Ein alter App-Stand darf eine administrative Zeitkorrektur nicht zurücksetzen.
    protected = set(db.scalars(select(WorkTimeChange.entry_id).join(WorkEntry).where(
        WorkEntry.work_month_id == period.id).with_for_update()).all())
    for item in batch.entries:
        entry = existing.get(str(item.client_id))
        lock = db.scalar(select(WorkEntryLock).where(WorkEntryLock.entry_id==entry.id).with_for_update()) if entry else None
        if lock and lock.locked:
            normalized=item.model_dump(mode='json')
            normalized['start']=item.start.strftime('%H:%M');normalized['end']=item.end.strftime('%H:%M')
            if normalized!=entry_dict(entry):
                raise HTTPException(409,"Arbeitszeitdatensatz ist gesperrt. Das gesamte Paket wurde nicht übernommen.")
        if entry and entry.id in protected and (entry.start_time,entry.end_time,entry.explicit_end_date) != (
                item.start.strftime('%H:%M'),item.end.strftime('%H:%M'),item.end_date):
            raise HTTPException(409, "Arbeitszeit wurde administrativ korrigiert. Aktuelle Monatsdaten vom Server laden.")
    for item in batch.entries:
        key = str(item.client_id)
        entry = existing.get(key)
        if entry is None:
            entry = WorkEntry(work_month_id=period.id, client_id=key)
            db.add(entry)
        entry.kind = item.kind
        entry.entry_date = item.date
        entry.start_time = item.start.strftime("%H:%M")
        entry.end_time = item.end.strftime("%H:%M")
        entry.pause_minutes = item.pause
        entry.guest_minutes = item.guest
        entry.note = item.note
        entry.away = item.away
        entry.accommodation = item.accommodation
        entry.hotel_name = item.hotel_name
        old_end_date=entry.explicit_end_date
        set_end_date(entry,item.end_date)
        if old_end_date!=item.end_date:entry.updated_at=now_utc()
    dispatch_id = None
    if batch.entries:
        db.flush()
        from .worktime.service import validate_no_overlap, overview
        try:
            for item in batch.entries:
                row=db.scalar(select(WorkEntry).where(WorkEntry.work_month_id==period.id,WorkEntry.client_id==str(item.client_id)))
                validate_no_overlap(db,user.id,row)
            periods={(year,month)}
            for item in batch.entries:
                row=db.scalar(select(WorkEntry).where(WorkEntry.work_month_id==period.id,WorkEntry.client_id==str(item.client_id)))
                periods.update(touched_months(row.entry_date,entry_end_date(row)))
            for y,m in periods:overview(db,user.id,y,m,profile.federal_state,lock=True)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(409,str(exc)) from exc
        received = db.scalars(select(WorkEntry).where(
            WorkEntry.work_month_id == period.id,
            WorkEntry.client_id.in_([str(item.client_id) for item in batch.entries]))).all()
        received_at = datetime.now(ZoneInfo("Europe/Berlin"))
        pdf_data = render_receipt_pdf(first_name=profile.first_name, last_name=profile.last_name,
                                      personnel_number=profile.personnel_number,
                                      federal_state=profile.federal_state, year=year, month=month,
                                      received_at=received_at,
                                      rows=day_rows(received, profile.federal_state))
        dispatch = ReportDispatch(tf_user_id=user.id, work_month_id=period.id,
                                  recipient_email=profile.email,
                                  filename=f"LokZeitleiste-Eingang-{year}-{month:02d}.pdf",
                                  pdf_data=pdf_data, status="pending")
        db.add(dispatch)
        db.flush()
        dispatch_id = dispatch.id
    if manual_actor is not None:
        from .models import WorkEntryAudit
        for entry in received:
            db.add(WorkEntryAudit(entry_id=entry.id,actor_id=manual_actor.id,action='manual_created'))
    db.commit()
    if dispatch_id is not None:
        background_tasks.add_task(process_dispatch, dispatch_id)
    return {"accepted": len(batch.entries), "year": year, "month": month,
            "email_status": "queued" if dispatch_id is not None else "no_entries",
            "report_dispatch_id": dispatch_id}


@app.get("/api/v1/me/months/{year}/{month}/entries")
def my_entries(year: int, month: int, user: User = Depends(require_tf), db: Session = Depends(database_session)):
    period = db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id == user.id,
                                              WorkMonth.year == year, WorkMonth.month == month))
    return [entry_dict(e) for e in period.entries] if period else []


from .planning.api import create_router
app.include_router(create_router(require_admin))


@app.get("/admin/planning")
def planning_page():
    return FileResponse(Path(__file__).parent / "static" / "planning.html")


@app.get("/admin/planning.js")
def planning_script():
    return FileResponse(Path(__file__).parent / "static" / "planning.js", media_type="text/javascript")


from .worktime.api import create_router as worktime_router
app.include_router(worktime_router(require_admin, month_summary, entry_dict))


@app.get("/admin/worktime")
def worktime_page():
    return FileResponse(Path(__file__).parent / "static" / "worktime.html")


@app.get("/admin/worktime.js")
def worktime_script():
    return FileResponse(Path(__file__).parent / "static" / "worktime.js", media_type="text/javascript")


from .accounts.api import create_router as account_router, account_dependency
require_account=account_dependency(lambda: PUBLIC_ORIGIN)
app.include_router(account_router(require_admin, lambda: PUBLIC_ORIGIN, COOKIE_SECURE,require_account))

from .records.api import create_router as records_router
app.include_router(records_router(require_account,require_admin,entry_dict,month_summary,persist_entries))

@app.get('/my/worktime')
def own_worktime_page():
    return FileResponse(Path(__file__).parent/'static'/'my-worktime.html')

@app.get('/my/worktime.js')
def own_worktime_script():
    return FileResponse(Path(__file__).parent/'static'/'my-worktime.js',media_type='text/javascript')

@app.get('/admin/tf/new')
@app.get('/admin/tf')
def tf_pages():
    return FileResponse(Path(__file__).parent/'static'/'admin.html')

@app.get('/responsive.css')
def responsive_css():
    return FileResponse(Path(__file__).parent/'static'/'responsive.css',media_type='text/css')

@app.get('/admin/photo-ui.js')
def photo_ui_script():
    return FileResponse(Path(__file__).parent/'static'/'photo-ui.js',media_type='text/javascript')

@app.get("/admin/staff")
def staff_page():
    return FileResponse(Path(__file__).parent / "static" / "staff.html")

@app.get("/admin/staff.js")
def staff_script():
    return FileResponse(Path(__file__).parent / "static" / "staff.js", media_type="text/javascript")

@app.get("/account")
def account_page():
    return FileResponse(Path(__file__).parent / "static" / "account.html")

@app.get("/account.js")
def account_script():
    return FileResponse(Path(__file__).parent / "static" / "account.js", media_type="text/javascript")

from .accounts.photos import create_router as photo_router
app.include_router(photo_router(require_admin))

@app.get('/entry-form.js')
def entry_form_script():
    return FileResponse(Path(__file__).parent/'static'/'entry-form.js',media_type='text/javascript')


from .tf_overview import create_router as tf_hours_router
app.include_router(tf_hours_router(require_admin, month_summary))

@app.get('/admin/tf/hours')
def tf_hours_page():
    return FileResponse(Path(__file__).parent/'static'/'tf-hours.html')

@app.get('/admin/tf/hours.js')
def tf_hours_script():
    return FileResponse(Path(__file__).parent/'static'/'tf-hours.js', media_type='text/javascript')
