"""Combined employee directory and reusable shift cycles."""
import json
from datetime import date, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import database_session
from .models import User, TfProfile, StaffProfile, ShiftModel, ShiftAssignment
from .planning.service import get_month, apply_days, RevisionConflict
from .planning.schemas import DayInput
from .planning.duties import duty_info, resolve_shift, driver_type


class CycleBlock(BaseModel):
    kind: Literal['Arbeitstag', 'Ruhetag']
    days: int = Field(ge=1, le=366)
    shift: Literal["standard","border_day","border_night"] = "standard"

    @model_validator(mode="after")
    def rest_shift(self):
        if self.kind=="Ruhetag":self.shift="standard"
        return self


class ModelInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    blocks: list[CycleBlock] = Field(min_length=1, max_length=30)
    expected_revision: int | None = None

    @model_validator(mode='after')
    def valid_cycle(self):
        self.name = self.name.strip()
        if not self.name or sum(b.days for b in self.blocks) > 366:
            raise ValueError('Name erforderlich; ein Zyklus darf höchstens 366 Tage lang sein.')
        return self


class AssignmentInput(BaseModel):
    model_id: int
    tf_id: int
    start: date
    end: date
    cycle_start: date
    overwrite: bool = False
    expected_model_revision: int
    expected_revisions: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode='after')
    def valid_dates(self):
        if not (2000 <= self.start.year <= 2100 and 2000 <= self.end.year <= 2100 and 2000 <= self.cycle_start.year <= 2100):
            raise ValueError('Jahre müssen zwischen 2000 und 2100 liegen.')
        if self.end < self.start or (self.end-self.start).days > 1830:
            raise ValueError('Zeitraum muss vorwärts liegen und darf höchstens fünf Jahre umfassen.')
        return self


def model_dict(model):
    return dict(id=model.id, name=model.name, blocks=json.loads(model.blocks), revision=model.revision)


def assignment_preview(db, data):
    model = db.scalar(select(ShiftModel).where(ShiftModel.id == data.model_id).with_for_update())
    user = db.get(User, data.tf_id)
    if not model or not user or user.role != 'tf':
        raise HTTPException(404, 'Schichtmodell oder Tf nicht gefunden')
    if model.revision != data.expected_model_revision:
        raise HTTPException(409, 'Schichtmodell wurde geändert. Bitte neu laden.')
    cycle = [b for b in json.loads(model.blocks) for _ in range(b['days'])]
    periods, revisions, days = {}, {}, []
    cursor = data.start
    skipped = 0
    while cursor <= data.end:
        key = f'{cursor.year}-{cursor.month:02d}'
        if key not in periods:
            periods[key] = get_month(db, data.tf_id, cursor.year, cursor.month)
            revisions[key] = periods[key]['revision']
        previous = periods[key]['days'][cursor.day-1]
        block=cycle[(cursor-data.cycle_start).days % len(cycle)];kind=block['kind']
        try:shift=resolve_shift(db,data.tf_id,kind,block.get('shift','standard'))
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        eligible = data.overwrite or previous['kind'] == 'Ungeplant'
        if not eligible:
            skipped += 1
        days.append(dict(previous, previous_kind=previous['kind'],previous_shift=previous['shift'], new_kind=kind,apply=eligible,**{('new_'+key):value for key,value in duty_info(cursor,kind,shift,previous['is_holiday']).items()}))
        cursor += timedelta(days=1)
    return dict(model=model_dict(model), days=days, expected_revisions=revisions, skipped_days=skipped,
                apply_days=sum(d['apply'] for d in days))


def create_router(require_admin):
    router = APIRouter(dependencies=[Depends(require_admin)])

    @router.get('/api/v1/admin/directory')
    def directory(db: Session = Depends(database_session)):
        rows = []
        for user, profile in db.execute(select(User, TfProfile).join(TfProfile).where(User.role == 'tf')):
            rows.append(dict(id=user.id, role='tf', first_name=profile.first_name, last_name=profile.last_name,
                             username=user.username, identifier=profile.personnel_number, active=user.active,driver_type=driver_type(db,user.id)))
        for user, profile in db.execute(select(User, StaffProfile).join(StaffProfile, User.id == StaffProfile.user_id).where(User.role == 'staff')):
            rows.append(dict(id=user.id, role='staff', first_name=profile.first_name, last_name=profile.last_name,
                             username=user.username, identifier=profile.cost_center, active=user.active))
        return sorted(rows, key=lambda row: (row['last_name'].casefold(), row['first_name'].casefold(), row['id']))

    @router.get('/api/v1/admin/shifts/models')
    def models(db: Session = Depends(database_session)):
        return [model_dict(m) for m in db.scalars(select(ShiftModel).order_by(ShiftModel.name))]

    @router.post('/api/v1/admin/shifts/models', status_code=201)
    def create_model(data: ModelInput, db: Session = Depends(database_session)):
        model = ShiftModel(name=data.name, blocks=json.dumps([b.model_dump() for b in data.blocks]), revision=1)
        db.add(model)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback(); raise HTTPException(409, 'Modellname bereits vorhanden') from exc
        return model_dict(model)

    @router.put('/api/v1/admin/shifts/models/{model_id}')
    def update_model(model_id: int, data: ModelInput, db: Session = Depends(database_session)):
        model = db.scalar(select(ShiftModel).where(ShiftModel.id == model_id).with_for_update())
        if not model:
            raise HTTPException(404, 'Schichtmodell nicht gefunden')
        if model.revision != data.expected_revision:
            raise HTTPException(409, 'Modell wurde zwischenzeitlich geändert. Bitte neu laden.')
        model.name, model.blocks = data.name, json.dumps([b.model_dump() for b in data.blocks])
        model.revision += 1
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback(); raise HTTPException(409, 'Modellname bereits vorhanden') from exc
        return model_dict(model)

    @router.post('/api/v1/admin/shifts/preview')
    def preview(data: AssignmentInput, db: Session = Depends(database_session)):
        return assignment_preview(db, data)

    @router.post('/api/v1/admin/shifts/assign')
    def assign(data: AssignmentInput, actor: User = Depends(require_admin), db: Session = Depends(database_session)):
        try:
            preview = assignment_preview(db, data)
            if preview['expected_revisions'] != data.expected_revisions:
                raise RevisionConflict('Plan zwischenzeitlich geändert')
            selected = [DayInput(date=date.fromisoformat(d['date']), kind=d['new_kind'], note='Schichtmodell: '+preview['model']['name'],shift=d['new_shift']) for d in preview['days'] if d['apply']]
            count = 0
            for year in sorted({d.date.year for d in selected}):
                days = [d for d in selected if d.date.year == year]
                revisions = {m: data.expected_revisions[f'{year}-{m:02d}'] for m in {d.date.month for d in days}}
                count += apply_days(db, tf_id=data.tf_id, year=year, days=days, revisions=revisions, admin_id=actor.id, source='shift')
            db.add(ShiftAssignment(model_id=data.model_id, tf_user_id=data.tf_id, admin_user_id=actor.id,
                                   start_date=data.start, end_date=data.end, cycle_start=data.cycle_start,
                                   model_snapshot=json.dumps(preview['model']), overwrite=data.overwrite, changed_days=count))
            db.commit()
            return dict(changed_days=count, skipped_days=preview['skipped_days'])
        except (RevisionConflict, IntegrityError) as exc:
            db.rollback(); raise HTTPException(409, 'Plan wurde geändert. Vorschau erneut laden.') from exc

    @router.get('/api/v1/admin/shifts/assignments')
    def assignments(db: Session = Depends(database_session)):
        return [dict(id=a.id, tf_id=a.tf_user_id, start=a.start_date.isoformat(), end=a.end_date.isoformat(),
                     cycle_start=a.cycle_start.isoformat(), model=json.loads(a.model_snapshot), changed_days=a.changed_days,
                     created_at=a.created_at.isoformat()) for a in db.scalars(select(ShiftAssignment).order_by(ShiftAssignment.id.desc()).limit(100))]
    return router
