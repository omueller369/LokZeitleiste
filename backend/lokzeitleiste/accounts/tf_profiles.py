"""TF employment, addresses, contract hours and one-time account migration."""
import calendar
import json
import secrets
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import select, delete, inspect, text
from ..models import User, TfProfile, TfEmployment, TfAddress, TfNumberMigration, SessionToken, RailwayStation, TfIdentity
from ..planning.holidays import berlin_holidays


def berlin_today():
    return datetime.now(ZoneInfo('Europe/Berlin')).date()


def ensure_gender_column(db):
    """create_all does not add columns to an existing v0.22 profile table."""
    if 'gender' not in {column['name'] for column in inspect(db.connection()).get_columns('tf_profiles')}:
        db.execute(text("ALTER TABLE tf_profiles ADD COLUMN gender VARCHAR(20) NOT NULL DEFAULT 'unspecified'"))


def migrate_legacy_gender(db):
    """Keep gender entered by the interim tf_profiles.gender implementation."""
    if 'gender' not in {column['name'] for column in inspect(db.connection()).get_columns('tf_profiles')}:
        return
    mapping={'männlich':'male','weiblich':'female','divers':'diverse','keine Angabe':'unspecified'}
    for user_id, value in db.execute(text('SELECT user_id, gender FROM tf_profiles')):
        if db.get(TfIdentity,user_id) is None:
            gender=mapping.get(value,value if value in mapping.values() else 'unspecified')
            db.add(TfIdentity(user_id=user_id,gender=gender))


def weekly_minutes(db, tf_id):
    row = db.get(TfEmployment, tf_id)
    return row.weekly_minutes if row else 2400


def daily_minutes(db, tf_id):
    return int((Decimal(weekly_minutes(db,tf_id))/5).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def monthly_minutes(db, tf_id, year, month):
    holidays = berlin_holidays(year)
    workdays = sum(date(year,month,d).weekday()<5 and date(year,month,d) not in holidays
                   for d in range(1,calendar.monthrange(year,month)[1]+1))
    return workdays*daily_minutes(db, tf_id)


def validate_details(db, data, user=None):
    if data.nationality is not None and data.nationality not in json.loads((Path(__file__).parent/'countries.json').read_text()):
        raise HTTPException(422,'Ungültige Staatsangehörigkeit.')
    if data.home_station and not db.get(RailwayStation,data.home_station.strip().upper()):
        raise HTTPException(422,'Heimatbahnhof bitte aus der Trefferliste wählen.')
    existing = db.get(TfEmployment,user.id) if user else None
    entry = data.entry_date if 'entry_date' in data.model_fields_set else existing.entry_date if existing else None
    exit = data.exit_date if 'exit_date' in data.model_fields_set else existing.exit_date if existing else None
    if entry and exit and exit < entry:
        raise HTTPException(422,'Austrittsdatum darf nicht vor dem Beitrittsdatum liegen.')
    if not user and (data.addresses is None or data.entry_date is None or data.weekly_minutes is None or data.nationality is None):
        raise HTTPException(422,'TF-Nummer, Beitrittsdatum, Wochenarbeitszeit, Staatsangehörigkeit und Adresse erforderlich.')


def save_details(db, user, data):
    old_name = user.username
    if data.username is not None: user.username = str(data.username)
    row = db.get(TfEmployment,user.id)
    if row is None:
        row = TfEmployment(user_id=user.id,tf_number=int(user.username),weekly_minutes=2400,immediate_block=False)
        db.add(row)
    identity=db.get(TfIdentity,user.id)
    if identity is None:
        identity=TfIdentity(user_id=user.id,gender=data.gender or "unspecified");db.add(identity)
    elif data.gender is not None:
        identity.gender=data.gender
    db.get(TfProfile,user.id).gender=identity.gender
    row.tf_number = int(user.username)
    for key in ('weekly_minutes','entry_date','exit_date','immediate_block','nationality','home_station'):
        if key in data.model_fields_set:
            value=getattr(data,key)
            if key in ('weekly_minutes','immediate_block') and value is None: continue
            if key=='home_station':value=value.strip().upper() if value else None
            setattr(row,key,value)
    if data.addresses is not None:
        db.execute(delete(TfAddress).where(TfAddress.user_id==user.id))
        for a in data.addresses:db.add(TfAddress(user_id=user.id,**a.model_dump()))
        postal=next(a for a in data.addresses if a.is_postal)
        db.get(TfProfile,user.id).federal_state=postal.federal_state
    if old_name != user.username or row.immediate_block or (row.exit_date and row.exit_date<=berlin_today()):
        db.execute(delete(SessionToken).where(SessionToken.user_id==user.id))
    db.flush()
    today=berlin_today()
    db.get(TfProfile,user.id).target_hours_minutes=monthly_minutes(db,user.id,today.year,today.month)


def details_dict(db,user):
    row=db.get(TfEmployment,user.id)
    identity=db.get(TfIdentity,user.id)
    addresses=[dict(id=a.id,street=a.street,house_number=a.house_number,postal_code=a.postal_code,
                    city=a.city,federal_state=a.federal_state,is_postal=a.is_postal)
               for a in db.scalars(select(TfAddress).where(TfAddress.user_id==user.id).order_by(TfAddress.id))]
    station=db.get(RailwayStation,row.home_station) if row and row.home_station else None
    today=berlin_today()
    return dict(gender=identity.gender if identity else "unspecified",tf_number=row.tf_number if row else int(user.username) if user.username.isdigit() else None,
                weekly_minutes=row.weekly_minutes if row else 2400,
                monthly_minutes=monthly_minutes(db,user.id,today.year,today.month),
                monthly_period=f'{today.year}-{today.month:02d}',
                entry_date=row.entry_date.isoformat() if row and row.entry_date else None,
                exit_date=row.exit_date.isoformat() if row and row.exit_date else None,
                immediate_block=bool(row and row.immediate_block),nationality=row.nationality if row else None,
                home_station=row.home_station if row else None,
                home_station_name=station.name if station else None,addresses=addresses)


def migrate_existing(db):
    """Atomic, idempotent migration. No renumbering after the companion row exists."""
    users=list(db.scalars(select(User).where(User.role=='tf').with_for_update()))
    pending=[u for u in users if db.get(TfEmployment,u.id) is None]
    pending_ids={u.id for u in pending}
    reserved={u.username for u in db.scalars(select(User)) if u.id not in pending_ids}
    available=[n for n in range(787000,788000) if str(n) not in reserved]
    if len(pending)>len(available):raise RuntimeError('Nicht genügend freie TF-Nummern mit Präfix 787; keine Migration durchgeführt.')
    secrets.SystemRandom().shuffle(available)
    today=berlin_today()
    originals={u.id:u.username for u in pending}
    for user in pending:
        if db.get(TfProfile,user.id) is None:raise RuntimeError('TF-Profil fehlt; keine Migration durchgeführt.')
    # Free numeric legacy names before assignment; all stages share one transaction.
    for user in pending:user.username='__tf_migration_'+str(user.id)+'_'+secrets.token_hex(12)
    db.flush()
    for user,number in zip(pending,available):
        profile=db.get(TfProfile,user.id)
        if not profile:raise RuntimeError('TF-Profil fehlt; keine Migration durchgeführt.')
        # Preserve a larger contractual workload; old input was monthly minutes.
        weekly=min(10080,max(2400,int((Decimal(profile.target_hours_minutes)*12/52).quantize(Decimal('1'),rounding=ROUND_HALF_UP))))
        db.add(TfNumberMigration(user_id=user.id,previous_username=originals[user.id],tf_number=number))
        user.username=str(number)
        db.add(TfEmployment(user_id=user.id,tf_number=number,weekly_minutes=weekly,immediate_block=False))
        db.execute(delete(SessionToken).where(SessionToken.user_id==user.id))
    db.flush()
    for user in pending:
        db.get(TfProfile,user.id).target_hours_minutes=monthly_minutes(db,user.id,today.year,today.month)
    return len(pending)


def seed_stations(db):
    if db.scalar(select(RailwayStation.code).limit(1)) is not None:return
    records=json.loads((Path(__file__).parent/'stations.json').read_text())
    db.bulk_insert_mappings(RailwayStation,records)
