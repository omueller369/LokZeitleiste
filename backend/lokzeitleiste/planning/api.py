from datetime import date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Path
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..db import database_session
from ..models import User, TfProfile, PlanChange
from .schemas import MonthInput, ImportInput
from .service import get_month, get_year, apply_days, RevisionConflict
from .excel import parse_excel, template, MAX_FILE
from .pdf import render_plan_pdf


def create_router(admin_dependency):
    router = APIRouter(prefix="/api/v1/admin/tf/{tf_id}/plan", tags=["Arbeitszeitplanung"],
                       dependencies=[Depends(admin_dependency)])

    def profile_for(db, tf_id):
        user, profile = db.get(User, tf_id), db.get(TfProfile, tf_id)
        if not user or user.role != "tf" or not profile:
            raise HTTPException(404, "Tf nicht gefunden")
        return profile

    def mutate(db, tf_id, year, days, revisions, admin, source):
        try:
            changes = apply_days(db, tf_id=tf_id, year=year, days=days,
                                 revisions=revisions, admin_id=admin.id, source=source)
            db.commit()
            db.expire_all()
            return changes
        except (RevisionConflict, IntegrityError) as exc:
            db.rollback()
            raise HTTPException(409, "Plan wurde inzwischen geändert. Bitte neu laden.") from exc
        except ValueError as exc:
            db.rollback()
            raise HTTPException(422, str(exc)) from exc

    @router.get("/{year}")
    def year_plan(tf_id: int, year: int = Path(ge=2000, le=2100), db: Session = Depends(database_session)):
        profile_for(db, tf_id)
        return get_year(db, tf_id, year)

    @router.get("/{year}/history")
    def history(tf_id: int, year: int = Path(ge=2000, le=2100), db: Session = Depends(database_session)):
        profile_for(db, tf_id)
        rows = db.scalars(select(PlanChange).where(PlanChange.tf_user_id == tf_id,
                          PlanChange.day >= date(year, 1, 1), PlanChange.day <= date(year, 12, 31))
                          .order_by(PlanChange.id.desc()).limit(100)).all()
        return [{"date": r.day.isoformat(), "previous_kind": r.previous_kind, "new_kind": r.new_kind,
                 "previous_note": r.previous_note, "new_note": r.new_note, "source": r.source,
                 "admin_id": r.admin_user_id, "changed_at": r.created_at.isoformat()} for r in rows]

    @router.get("/{year}/template.xlsx")
    def excel_template(tf_id: int, year: int = Path(ge=2000, le=2100), db: Session = Depends(database_session)):
        profile = profile_for(db, tf_id)
        return Response(template(get_year(db, tf_id, year), profile.personnel_number),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="LokZeitleiste-Plan-{tf_id}-{year}.xlsx"'})

    @router.post("/{year}/import/preview")
    async def preview(tf_id: int, year: int = Path(ge=2000, le=2100),
                      file: UploadFile = File(...), db: Session = Depends(database_session)):
        profile = profile_for(db, tf_id)
        try:
            if not file.filename or not file.filename.lower().endswith(".xlsx"):
                raise HTTPException(422, "Bitte eine XLSX-Datei auswählen")
            content = await file.read(MAX_FILE + 1)
            try:
                days = parse_excel(content, year=year, personnel_number=profile.personnel_number)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            cached = {m: get_month(db, tf_id, year, m) for m in sorted({d.date.month for d in days})}
            revisions = {m: period["revision"] for m, period in cached.items()}
            updates = []
            for item in days:
                old = cached[item.date.month]["days"][item.date.day - 1]
                updates.append({**item.model_dump(mode="json"), "previous_kind": old["kind"],
                                "previous_note": old["note"]})
            return {"days": updates, "expected_revisions": revisions,
                    "rule": "Nur enthaltene Datumszeilen werden geändert. Ungeplant entfernt eine Tagesplanung."}
        finally:
            await file.close()

    @router.post("/{year}/import")
    def import_plan(tf_id: int, data: ImportInput, year: int = Path(ge=2000, le=2100),
                    admin: User = Depends(admin_dependency), db: Session = Depends(database_session)):
        profile_for(db, tf_id)
        changes = mutate(db, tf_id, year, data.days, data.expected_revisions, admin, "excel")
        return {"changed_days": changes, "plan": get_year(db, tf_id, year)}

    @router.post("/{year}/bulk")
    def bulk_plan(tf_id: int, data: ImportInput, year: int = Path(ge=2000, le=2100),
                  admin: User = Depends(admin_dependency), db: Session = Depends(database_session)):
        profile_for(db, tf_id)
        changes = mutate(db, tf_id, year, data.days, data.expected_revisions, admin, "manual")
        return {"changed_days": changes, "plan": get_year(db, tf_id, year)}

    @router.get("/{year}/pdf")
    def year_pdf(tf_id: int, year: int = Path(ge=2000, le=2100), db: Session = Depends(database_session)):
        p = profile_for(db, tf_id)
        data = render_plan_pdf(get_year(db, tf_id, year), name=f"{p.first_name} {p.last_name}", personnel_number=p.personnel_number, yearly=True)
        return Response(data, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="LokZeitleiste-Jahresplan-{tf_id}-{year}.pdf"'})

    @router.get("/{year}/{month}/pdf")
    def month_pdf(tf_id: int, year: int = Path(ge=2000, le=2100), month: int = Path(ge=1, le=12), db: Session = Depends(database_session)):
        p = profile_for(db, tf_id)
        data = render_plan_pdf(get_month(db, tf_id, year, month), name=f"{p.first_name} {p.last_name}", personnel_number=p.personnel_number)
        return Response(data, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="LokZeitleiste-Monatsplan-{tf_id}-{year}-{month:02d}.pdf"'})

    @router.get("/{year}/{month}")
    def month_plan(tf_id: int, year: int = Path(ge=2000, le=2100), month: int = Path(ge=1, le=12), db: Session = Depends(database_session)):
        profile_for(db, tf_id)
        return get_month(db, tf_id, year, month)

    @router.put("/{year}/{month}")
    def edit_month(tf_id: int, data: MonthInput, year: int = Path(ge=2000, le=2100),
                   month: int = Path(ge=1, le=12), admin: User = Depends(admin_dependency), db: Session = Depends(database_session)):
        profile_for(db, tf_id)
        if any(d.date.year != year or d.date.month != month for d in data.days):
            raise HTTPException(422, "Alle Tage müssen zum ausgewählten Monat gehören")
        mutate(db, tf_id, year, data.days, {month: data.expected_revision}, admin, "manual")
        return get_month(db, tf_id, year, month)

    return router
