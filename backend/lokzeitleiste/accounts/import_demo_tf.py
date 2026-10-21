"""Add the packaged twenty demo TF without deleting existing accounts or work data."""
import argparse
import json
from contextlib import ExitStack
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Base, engine
from ..models import (User, TfProfile, TfEmployment, TfDutyProfile, TfIdentity,
                      TfAddress, TfBahnCardValidity, ProfilePhoto, AccountPolicy, AccountAudit)
from ..security import hash_password
from ..user_directories import directory_transaction, storage_root
from .seed_demo_tf import build_records, validate_records, DATA, PASSWORD, EMAIL
from .photos import normalize
from .tf_profiles import berlin_today, monthly_minutes, ensure_gender_column

PREFIX = 'demo_tf_import_v1:'


def import_demo_tf(db, today=None, seed=23):
    """Caller owns transaction and directory provisioning. Existing accounts are never reset."""
    today = today or berlin_today()
    actor = db.scalar(select(User).where(User.role == 'admin').order_by(User.id).limit(1).with_for_update())
    if not actor:
        raise ValueError('Zuerst einen Administrator anlegen.')
    folder = storage_root() / 'TF'
    if folder.is_symlink():
        raise ValueError('Ungültiger TF-Verzeichnisroot.')
    reserved = list(db.scalars(select(User.username)))
    if folder.is_dir():
        reserved.extend(path.name for path in folder.iterdir())
    # Generate before inserting. Fewer than 20 free numbers only matter for NEW people.
    records = build_records(today, seed=seed)
    validate_records(records, today)
    photos = []
    for record in records:
        path = DATA / record['photo']
        if not path.is_file():
            raise ValueError(f'Fiktives Profilbild fehlt: {record["photo"]}')
        photos.append(normalize(path.read_bytes()))
    markers = {}
    candidates = []
    for record, photo in zip(records, photos):
        action = PREFIX + record['photo']
        tracked = db.scalars(select(AccountAudit).where(AccountAudit.action == action)).all()
        tracked_ids = {item.target_id for item in tracked}
        if len(tracked_ids) > 1:
            raise ValueError('Mehrdeutige Testdaten-Zuordnung: ' + record['first_name'] + ' ' + record['last_name'])
        if tracked_ids:
            user = db.get(User, next(iter(tracked_ids)))
            if not user or user.role != 'tf' or not db.get(TfProfile, user.id):
                raise ValueError('Ungültige vorhandene Testdaten-Zuordnung.')
            markers[action] = user
            continue
        matches = db.scalars(select(User).join(TfProfile).where(
            User.role == 'tf', TfProfile.first_name == record['first_name'],
            TfProfile.last_name == record['last_name'], TfProfile.email == EMAIL)).all()
        if len(matches) > 1:
            raise ValueError('Testperson mehrfach vorhanden; zuerst administrativ prüfen: ' + record['last_name'])
        if matches:
            existing = db.get(ProfilePhoto, matches[0].id)
            if existing and existing.image_data != photo:
                raise ValueError('Abweichendes vorhandenes Foto; keine Daten überschrieben: ' + record['last_name'])
            markers[action] = matches[0]
        else:
            candidates.append(record)
    unavailable = set(reserved)
    available = [str(number) for number in range(787000, 788000) if str(number) not in unavailable]
    if len(available) < len(candidates):
        raise ValueError('Nicht genügend freie TF-Nummern mit Präfix 787.')
    used_personnel = set(db.scalars(select(TfProfile.personnel_number)))
    result = dict(created=0, existing=0, photos_restored=0, people=[])
    for record, photo in zip(records, photos):
        action = PREFIX + record['photo']
        user = markers.get(action)
        if user:
            result['existing'] += 1
            if db.get(ProfilePhoto, user.id) is None:
                db.add(ProfilePhoto(user_id=user.id, image_data=photo))
                result['photos_restored'] += 1
        else:
            username = record['username']
            if username in unavailable:
                username = next(number for number in available if number not in unavailable)
            unavailable.add(username)
            personnel = record['personnel_number']
            if personnel in used_personnel:
                personnel = next((f'{number:05d}' for number in range(100000)
                                  if f'{number:05d}' not in used_personnel), None)
                if personnel is None:
                    raise ValueError('Keine freie fünfstellige Personalnummer vorhanden.')
            used_personnel.add(personnel)
            user = User(username=username, password_hash=hash_password(PASSWORD), role='tf', active=True)
            db.add(user); db.flush()
            db.add(AccountPolicy(user_id=user.id, must_change_password=True))
            db.add(TfProfile(user_id=user.id, first_name=record['first_name'], last_name=record['last_name'],
                             personnel_number=personnel, target_hours_minutes=0, vacation_days=30,
                             birth_date=record['birth_date'], bahncard=record['bahncard'], gender=record['gender'],
                             email=EMAIL, federal_state=record['federal_state']))
            db.add(TfEmployment(user_id=user.id, tf_number=int(username), weekly_minutes=2400,
                                entry_date=record['entry_date'], exit_date=None, immediate_block=False,
                                nationality='DE'))
            db.add(TfIdentity(user_id=user.id, gender=record['gender']))
            db.add(TfDutyProfile(user_id=user.id, driver_type=record['driver_type']))
            for address in record['addresses']:
                db.add(TfAddress(user_id=user.id, **address))
            if record['bahncard']:
                db.add(TfBahnCardValidity(user_id=user.id, valid_until=record['bahncard_valid_until']))
            db.add(ProfilePhoto(user_id=user.id, image_data=photo))
            db.flush()
            db.get(TfProfile, user.id).target_hours_minutes = monthly_minutes(db, user.id, today.year, today.month)
            result['created'] += 1
        if not db.scalar(select(AccountAudit.id).where(AccountAudit.action == action, AccountAudit.target_id == user.id)):
            db.add(AccountAudit(actor_id=actor.id, target_id=user.id, action=action))
        db.flush()
        profile = db.get(TfProfile, user.id)
        result['people'].append(dict(id=user.id, username=user.username, first_name=profile.first_name,
                                     last_name=profile.last_name, personnel_number=profile.personnel_number))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=23)
    args = parser.parse_args()
    Base.metadata.create_all(engine())
    with Session(engine()) as db:
        ensure_gender_column(db); db.commit()
    with Session(engine()) as db:
        try:
            with ExitStack() as stack:
                result = import_demo_tf(db, seed=args.seed)
                for person in result['people']:
                    stack.enter_context(directory_transaction(db.get(User, person['id'])))
                db.commit()
        except Exception:
            db.rollback()
            raise
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
