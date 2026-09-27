import os
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import database_session
from .models import TfProfile, User, WorkEntry, WorkMonth
from .schemas import Credentials, EntryBatch, TfCreate
from .security import issue_token, revoke_token, user_from_token, verify_password, hash_password


app = FastAPI(title="LokZeitleiste API", version="0.5")
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
                         vacation_days=data.vacation_days, birth_date=data.birth_date, bahncard=data.bahncard))
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
             "birth_date": p.birth_date.isoformat(), "bahncard": p.bahncard} for user, p in rows]


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
def upload_entries(year: int, month: int, batch: EntryBatch, user: User = Depends(require_tf),
                   db: Session = Depends(database_session)):
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        raise HTTPException(422, "Ungültiger Monat")
    if any(e.date.year != year or e.date.month != month for e in batch.entries):
        raise HTTPException(422, "Eintrag gehört nicht zum angeforderten Monat")
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
    db.commit()
    return {"accepted": len(batch.entries), "year": year, "month": month}


@app.get("/api/v1/me/months/{year}/{month}/entries")
def my_entries(year: int, month: int, user: User = Depends(require_tf), db: Session = Depends(database_session)):
    period = db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id == user.id,
                                              WorkMonth.year == year, WorkMonth.month == month))
    return [entry_dict(e) for e in period.entries] if period else []
