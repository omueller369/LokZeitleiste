"""Private TF notes: every read and mutation is scoped to the authenticated owner."""
from .localization import source as _text_source
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from .db import database_session
from .models import TfNote, User, now_utc
from .tf_portal import driver_dependency


class NoteInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=1000)

    @field_validator('title')
    @classmethod
    def clean_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError(_text_source('server_notes.text_450e6fe4fba6'))
        return value

    @field_validator('text')
    @classmethod
    def nonempty_text(cls, value):
        if not value.strip():
            raise ValueError(_text_source('server_notes.text_e5ebdff39d10'))
        return value


class NoteUpdate(NoteInput):
    expected_revision: int = Field(ge=1)


def note_dict(note, full=True):
    result = dict(id=note.id, title=note.title, revision=note.revision,
                  created_at=note.created_at.isoformat()+'Z',
                  updated_at=note.updated_at.isoformat()+'Z')
    if full:
        result['text'] = note.text
    return result


def create_router(require_account):
    router = APIRouter()
    require_driver = driver_dependency(require_account)

    def own_note(db, user, note_id):
        note = db.scalar(select(TfNote).where(TfNote.id == note_id, TfNote.owner_id == user.id))
        if note is None:
            raise HTTPException(404, _text_source('server_notes.text_cb9758f208b8'))
        return note

    @router.get('/api/v1/tf/notes')
    def listing(user: User = Depends(require_driver), db: Session = Depends(database_session)):
        rows = db.scalars(select(TfNote).where(TfNote.owner_id == user.id)
                          .order_by(TfNote.created_at.desc(), TfNote.id.desc())).all()
        return [note_dict(note, full=False) for note in rows]

    @router.post('/api/v1/tf/notes', status_code=201)
    def create(data: NoteInput, user: User = Depends(require_driver), db: Session = Depends(database_session)):
        note = TfNote(owner_id=user.id, title=data.title, text=data.text)
        db.add(note)
        db.commit()
        db.refresh(note)
        return note_dict(note)

    @router.get('/api/v1/tf/notes/{note_id}')
    def detail(note_id: int, user: User = Depends(require_driver), db: Session = Depends(database_session)):
        return note_dict(own_note(db, user, note_id))

    @router.put('/api/v1/tf/notes/{note_id}')
    def edit(note_id: int, data: NoteUpdate, user: User = Depends(require_driver), db: Session = Depends(database_session)):
        own_note(db, user, note_id)
        result = db.execute(update(TfNote).where(
            TfNote.id == note_id, TfNote.owner_id == user.id, TfNote.revision == data.expected_revision
        ).values(title=data.title, text=data.text, revision=TfNote.revision+1, updated_at=now_utc()),
                            execution_options={'synchronize_session': False})
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, _text_source('server_notes.text_97ff6284277e'))
        db.commit()
        db.expire_all()
        return note_dict(own_note(db, user, note_id))

    @router.delete('/api/v1/tf/notes/{note_id}')
    def remove(note_id: int, expected_revision: int = Query(ge=1),
               user: User = Depends(require_driver), db: Session = Depends(database_session)):
        own_note(db, user, note_id)
        result = db.execute(delete(TfNote).where(
            TfNote.id == note_id, TfNote.owner_id == user.id, TfNote.revision == expected_revision),
                            execution_options={'synchronize_session': False})
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, _text_source('server_notes.text_143ea716db68'))
        db.commit()
        return {'deleted': note_id}

    return router
