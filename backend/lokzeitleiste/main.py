import os
from pathlib import Path

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import database_session
from .models import ReportDispatch, TfProfile, User, WorkEntry, WorkMonth
from .schemas import Credentials, EntryBatch, TfCreate, TfDeliveryUpdate
from .security import issue_token, revoke_token, user_from_token, verify_password, hash_password
from .reports.daily import day_rows
from .reports.mailer import smtp_configured
from .reports.pdf import render_receipt_pdf
from .reports.monthly import summarize_month
from .reports.service import process_dispatch


app = FastAPI(title="LokZeitleiste API", version="0.7")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
PUBLIC_ORIGIN = os.getenv("PUBLIC_ORIGIN", "")


def require_tf(authorization: str | None = Header(default=None), db: Session = Depends(database_session)) -> User:
    token = authorization.removeprefix("Bearer ").strip() if authorization and authorization.startswith("Bearer ") else ""
    user = user_from_token(db, token)
    if not user or user.role != "tf":
        raise HTTPException(401, "Tf-Anmeldung erforderlich")
    return user


def require_admin(request: Request, admin_session: str | None = Cookie(default=None),
                  db: Session = Depends(database_session)) -> User:
    user = user_from_token(db, admin_session)
    if not user or user.role != "admin":
        raise HTTPException(401, "Admin-Anmeldung erforderlich")
    if request.method not in ("GET", "HEAD") and PUBLIC_ORIGIN and request.headers.get("origin") != PUBLIC_ORIGIN:
        raise HTTPException(403, "Ungültiger Ursprung")
    return user


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/admin")
def admin_page():
    return FileResponse(Path(__file__).parent / "static" / "admin.html")


@app.post("/api/v1/admin/login")
def admin_login(credentials: Credentials, response: Response, db: Session = Depends(database_session)):
    user = db.scalar(select(User).where(User.username == credentials.username.lower(), User.role == "admin"))
    if not user or not user.active or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(401, "Anmeldung fehlgeschlagen")
    token = issue_token(db, user)
    response.set_cookie("admin_session", token, httponly=True, secure=COOKIE_SECURE,
                        samesite="strict", max_age=365 * 24 * 3600, path="/")
    return {"username": user.username}


@app.post("/api/v1/admin/logout")
def admin_logout(response: Response, admin_session: str | None = Cookie(default=None),
                 _: User = Depends(require_admin), db: Session = Depends(database_session)):
    if admin_session:
        revoke_token(db, admin_session)
    response.delete_cookie("admin_session", path="/")
    return {"ok": True}


@app.post("/api/v1/admin/tf", status_code=201)
def create_tf(data: TfCreate, _: User = Depends(require_admin), db: Session = Depends(database_session)):
    username = data.username.strip().lower()
    if not username or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for c in username):
        raise HTTPException(422, "Ungültiger Benutzername")
    try:
        user = User(username=username, password_hash=hash_password(data.password), role="tf")
        db.add(user)
        db.flush()
        db.add(TfProfile(user_id=user.id, last_name=data.last_name.strip(), first_name=data.first_name.strip(),
                         personnel_number=data.personnel_number.strip(),
                         target_hours_minutes=data.target_hours_minutes,
                         vacation_days=data.vacation_days, birth_date=data.birth_date, bahncard=data.bahncard,
                         email=str(data.email), federal_state=data.federal_state))
        db.commit()
        return {"id": user.id, "username": user.username}
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Benutzername oder Personalnummer bereits vorhanden")


@app.get("/api/v1/admin/tf")
def list_tf(_: User = Depends(require_admin), db: Session = Depends(database_session)):
    rows = db.execute(select(User, TfProfile).join(TfProfile).where(User.role == "tf").order_by(TfProfile.last_name)).all()
    return [{"id": user.id, "username": user.username, "active": user.active,
             "last_name": p.last_name, "first_name": p.first_name, "personnel_number": p.personnel_number,
             "target_hours_minutes": p.target_hours_minutes, "vacation_days": p.vacation_days,
             "birth_date": p.birth_date.isoformat(), "bahncard": p.bahncard,
             "email": p.email, "federal_state": p.federal_state} for user, p in rows]


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
    periods = [(year, month)]
    periods.append((year - 1, 12) if month == 1 else (year, month - 1))
    entries = []
    for y, m in periods:
        period = db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id == tf_id,
                                                  WorkMonth.year == y, WorkMonth.month == m))
        if period:
            entries.extend(period.entries)
    try:
        result = summarize_month(entries, year=year, month=month, federal_state=profile.federal_state)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    result["tf_user_id"] = tf_id
    today = datetime.now(ZoneInfo("Europe/Berlin"))
    result["status"] = "vorläufig" if (year, month) >= (today.year, today.month) else "Monatsende"
    return result


@app.get("/api/v1/admin/tf/{tf_id}/months/{year}/{month}/summary")
def admin_month_summary(tf_id: int, year: int, month: int, _: User = Depends(require_admin),
                        db: Session = Depends(database_session)):
    user = db.get(User, tf_id)
    if not user or user.role != "tf":
        raise HTTPException(404, "Tf nicht gefunden")
    return month_summary(db, tf_id, year, month)


@app.get("/api/v1/me/months/{year}/{month}/summary")
def my_month_summary(year: int, month: int, user: User = Depends(require_tf),
                     db: Session = Depends(database_session)):
    return month_summary(db, user.id, year, month)


@app.post("/api/v1/tf/login")
def tf_login(credentials: Credentials, db: Session = Depends(database_session)):
    user = db.scalar(select(User).where(User.username == credentials.username.lower(), User.role == "tf"))
    if not user or not user.active or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(401, "Anmeldung fehlgeschlagen")
    return {"access_token": issue_token(db, user), "token_type": "bearer", "username": user.username}


@app.post("/api/v1/tf/logout")
def tf_logout(authorization: str | None = Header(default=None), _: User = Depends(require_tf),
              db: Session = Depends(database_session)):
    if authorization:
        revoke_token(db, authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


def entry_dict(e: WorkEntry):
    return {"client_id": e.client_id, "kind": e.kind, "date": e.entry_date.isoformat(),
            "start": e.start_time, "end": e.end_time, "pause": e.pause_minutes,
            "guest": e.guest_minutes, "note": e.note, "away": e.away,
            "accommodation": e.accommodation, "hotel_name": e.hotel_name}


@app.post("/api/v1/me/months/{year}/{month}/entries")
def upload_entries(year: int, month: int, batch: EntryBatch, background_tasks: BackgroundTasks,
                   user: User = Depends(require_tf),
                   db: Session = Depends(database_session)):
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        raise HTTPException(422, "Ungültiger Monat")
    if any(e.date.year != year or e.date.month != month for e in batch.entries):
        raise HTTPException(422, "Eintrag gehört nicht zum angeforderten Monat")
    profile = db.get(TfProfile, user.id)
    if not profile or not profile.email or not profile.federal_state:
        raise HTTPException(409, "E-Mail-Adresse und Bundesland des Tf fehlen im Admin-Profil")
    if batch.entries and not smtp_configured():
        raise HTTPException(503, "E-Mail-Versand ist auf dem Server noch nicht eingerichtet")
    period = db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id == user.id,
                                              WorkMonth.year == year, WorkMonth.month == month))
    if not period:
        period = WorkMonth(tf_user_id=user.id, year=year, month=month)
        db.add(period)
        db.flush()
    existing = {e.client_id: e for e in period.entries}
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
    dispatch_id = None
    if batch.entries:
        db.flush()
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
