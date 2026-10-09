from datetime import datetime, time, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import database_session
from ..models import TfProfile, User, WorkEntry, WorkMonth, WorkTimeChange, now_utc
from ..schemas import EntryIn
from ..reports.daily import WORK_KINDS
from ..reports.mailer import smtp_configured
from .service import change_body, overview, process_change, validate_no_overlap


class TimeEdit(BaseModel):
    start: time
    end: time
    expected_updated_at: datetime
    reason: str = Field(min_length=1, max_length=1000)


def create_router(require_admin, month_summary, entry_dict):
    router = APIRouter(prefix="/api/v1/admin/tf/{tf_id}/worktime", dependencies=[Depends(require_admin)])

    def profile_for(db, tf_id):
        user, profile = db.get(User, tf_id), db.get(TfProfile, tf_id)
        if not user or user.role != "tf" or not profile:
            raise HTTPException(404, "Mitarbeiter nicht gefunden")
        if not profile.federal_state:
            raise HTTPException(409, "Bundesland des Mitarbeiters fehlt")
        return profile

    @router.get("/months/{year}/{month}")
    def get_overview(tf_id: int, year: int, month: int, db: Session = Depends(database_session)):
        profile = profile_for(db, tf_id)
        summary = month_summary(db, tf_id, year, month)
        try:
            result = overview(db, tf_id, year, month, profile.federal_state)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        period = db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id == tf_id,
                          WorkMonth.year == year, WorkMonth.month == month))
        result["entries"] = [dict(entry_dict(e), id=e.id, updated_at=e.updated_at.isoformat(),
                                  editable=e.kind in WORK_KINDS) for e in sorted(period.entries,
                                  key=lambda e: (e.entry_date, e.start_time, e.id))] if period else []
        result["month"] = summary
        return result

    @router.get("/changes/history")
    def history(tf_id: int, db: Session = Depends(database_session)):
        profile_for(db, tf_id)
        items = db.scalars(select(WorkTimeChange).where(WorkTimeChange.tf_user_id == tf_id)
                           .order_by(WorkTimeChange.id.desc()).limit(100)).all()
        return [{"id": c.id, "entry_id": c.entry_id, "date": c.entry_date.isoformat(),
                 "previous_start": c.previous_start, "previous_end": c.previous_end,
                 "new_start": c.new_start, "new_end": c.new_end, "reason": c.reason,
                 "admin_id": c.admin_user_id, "created_at": c.created_at.isoformat(),
                 "recipient_email": c.recipient_email, "email_status": c.status,
                 "attempts": c.attempts, "last_error": c.last_error} for c in items]

    @router.patch("/entries/{entry_id}")
    def edit(tf_id: int, entry_id: int, data: TimeEdit, tasks: BackgroundTasks,
             admin: User = Depends(require_admin), db: Session = Depends(database_session)):
        db.scalar(select(User).where(User.id == tf_id).with_for_update())
        profile = profile_for(db, tf_id)
        period = db.scalar(select(WorkMonth).join(WorkEntry).where(
            WorkMonth.tf_user_id == tf_id, WorkEntry.id == entry_id).with_for_update())
        if not period:
            raise HTTPException(404, "Eintrag des Mitarbeiters nicht gefunden")
        entry = db.scalar(select(WorkEntry).where(WorkEntry.id == entry_id).with_for_update())
        if entry.kind not in WORK_KINDS:
            raise HTTPException(422, "Nur erfasste Arbeitszeiten können korrigiert werden")
        if data.expected_updated_at.tzinfo or entry.updated_at != data.expected_updated_at:
            raise HTTPException(409, "Eintrag wurde inzwischen geändert. Bitte neu laden.")
        reason = data.reason.strip()
        if not reason:
            raise HTTPException(422, "Änderungsgrund erforderlich")
        try:
            validated = EntryIn.model_validate(dict(entry_dict(entry), start=data.start, end=data.end))
        except ValidationError as exc:
            raise HTTPException(422, "Ungültiger Zeitraum: " + str(exc.errors()[0]["msg"])) from exc
        new_start, new_end = validated.start.strftime("%H:%M"), validated.end.strftime("%H:%M")
        if (entry.start_time, entry.end_time) == (new_start, new_end):
            return {"changed": False, "email_status": "unchanged"}
        if not profile.email:
            raise HTTPException(409, "E-Mail-Adresse des Mitarbeiters fehlt")
        if not smtp_configured():
            raise HTTPException(503, "E-Mail-Versand ist auf dem Server noch nicht eingerichtet")
        # Jede Schicht kann höchstens bis zum Folgetag reichen, auch über Monats-/Jahresgrenzen.
        next_day = entry.entry_date + timedelta(days=1)
        periods = {(entry.entry_date.year, entry.entry_date.month), (next_day.year, next_day.month)}
        try:
            before = {p: overview(db, tf_id, *p, profile.federal_state, lock=True) for p in periods}
            old_start, old_end = entry.start_time, entry.end_time
            entry.start_time, entry.end_time = new_start, new_end
            entry.updated_at = now_utc()
            validate_no_overlap(db, tf_id, entry)
            db.flush()
            after = {p: overview(db, tf_id, *p, profile.federal_state, lock=True) for p in periods}
        except ValueError as exc:
            db.rollback()
            raise HTTPException(409, str(exc)) from exc
        change = WorkTimeChange(entry_id=entry.id, tf_user_id=tf_id, admin_user_id=admin.id,
            entry_date=entry.entry_date, previous_start=old_start, previous_end=old_end,
            new_start=new_start, new_end=new_end, reason=reason, recipient_email=profile.email,
            email_body=change_body(profile, entry, old_start, old_end, reason, before, after), status="pending")
        db.add(change)
        db.flush()
        change_id = change.id
        db.commit()
        tasks.add_task(process_change, change_id)
        return {"changed": True, "change_id": change_id, "email_status": "queued"}

    @router.post("/changes/{change_id}/retry")
    def retry(tf_id: int, change_id: int, tasks: BackgroundTasks, db: Session = Depends(database_session)):
        item = db.scalar(select(WorkTimeChange).where(WorkTimeChange.id == change_id,
                          WorkTimeChange.tf_user_id == tf_id).with_for_update())
        if not item:
            raise HTTPException(404, "Änderung nicht gefunden")
        if item.status != "failed":
            raise HTTPException(409, "Nur fehlgeschlagene Benachrichtigungen können erneut gestartet werden")
        if not smtp_configured():
            raise HTTPException(503, "E-Mail-Versand ist noch nicht eingerichtet")
        item.status, item.attempts, item.last_error = "pending", 0, ""
        db.commit()
        tasks.add_task(process_change, change_id)
        return {"email_status": "queued"}

    return router
