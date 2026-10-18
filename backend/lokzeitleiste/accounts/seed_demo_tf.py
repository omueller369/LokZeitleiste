"""Explicit replacement of all TF records with twenty fictional test accounts."""
import argparse
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from sqlalchemy import select, delete, or_, func
from sqlalchemy.orm import Session
from ..db import Base, engine
from ..models import User, TfProfile, AccountPolicy, TfEmployment, TfDutyProfile, TfIdentity, TfAddress, TfBahnCardValidity, ProfilePhoto
from ..security import hash_password
from .photos import normalize
from .tf_profiles import berlin_today, monthly_minutes

DATA=Path(__file__).parent/'demo_tf'
PASSWORD='tomcom123456'
EMAIL='omueller369@gmail.com'
STATES=[('BE','Berlin','10115'),('BW','Stuttgart','70173'),('BY','München','80331'),
        ('BB','Potsdam','14467'),('HB','Bremen','28195'),('HH','Hamburg','20095'),
        ('HE','Wiesbaden','65183'),('MV','Schwerin','19053'),('NI','Hannover','30159'),
        ('NW','Düsseldorf','40213'),('RP','Mainz','55116'),('SH','Kiel','24103'),
        ('SL','Saarbrücken','66111'),('SN','Dresden','01067'),('ST','Magdeburg','39104'),
        ('TH','Erfurt','99084')]


def year_shift(day, years):
    try:return day.replace(year=day.year+years)
    except ValueError:return day.replace(year=day.year+years,day=28)


def random_date(rng,start,end):
    return start+timedelta(days=rng.randrange((end-start).days+1))


def build_records(today=None, seed=None, unavailable=()):
    today=today or berlin_today()
    rng=random.Random(seed)
    people=json.loads((DATA/'people.json').read_text())
    available=[n for n in range(787000,788000) if str(n) not in {str(v) for v in unavailable}]
    if len(available)<20:raise ValueError('Nicht genügend freie TF-Nummern mit Präfix 787.')
    numbers=rng.sample(available,20)
    personnel=['00001']+[f'{n:05d}' for n in rng.sample(range(10000,100000),19)]
    locations=STATES+[("BE","Berlin","10117"),("BE","Berlin","10243"),("BE","Berlin","10557"),("SN","Leipzig","04109")]
    rng.shuffle(locations)
    validity=rng.sample(range(120,366),19)
    records=[]
    for index,person in enumerate(people):
        age=person['age']
        birth=random_date(rng,year_shift(today,-age-1)+timedelta(days=1),year_shift(today,-age))
        entry=random_date(rng,max(date(1995,1,1),year_shift(birth,18)),today)
        state,city,postal=locations[index]
        records.append(dict(first_name=person['first_name'],last_name=person['last_name'],gender=person['gender'],
            username=str(numbers[index]),tf_number=numbers[index],personnel_number=personnel[index],
            driver_type='border' if index<3 else 'both' if index<5 else 'route',
            weekly_minutes=2400,vacation_days=30,birth_date=birth,entry_date=entry,
            bahncard=100 if index<18 else 50 if index==18 else 0,
            bahncard_valid_until=today+timedelta(days=validity[index]) if index<19 else None,
            email=EMAIL,nationality='DE',federal_state=state,
            addresses=[dict(street=f'Fiktive Teststraße {index+1}',house_number=str(rng.randrange(1,100)),
                            postal_code=postal,city=city,federal_state=state,is_postal=True)],photo=person['photo']))
    return records


def validate_records(records,today):
    if len(records)!=20:raise ValueError('Genau 20 Testpersonen erforderlich.')
    if Counter(r['gender'] for r in records)!=Counter(male=14,female=4,diverse=1,unspecified=1):raise ValueError('Ungültige Geschlechtsverteilung.')
    if Counter(r['driver_type'] for r in records)!=Counter(route=15,border=3,both=2):raise ValueError('Ungültige TF-Typen.')
    if Counter(r['bahncard'] for r in records)!=Counter({100:18,50:1,0:1}):raise ValueError('Ungültige BahnCard-Verteilung.')
    if len({r['username'] for r in records})!=20 or any(len(r['username'])!=6 or not r['username'].startswith('787') or not r['username'].isdigit() for r in records):raise ValueError('Ungültige TF-Nummern.')
    if len({r['personnel_number'] for r in records})!=20 or any(len(r['personnel_number'])!=5 or not r['personnel_number'].isdigit() for r in records):raise ValueError('Ungültige Personalnummern.')
    if len({r['federal_state'] for r in records})!=16 or sum(r['federal_state']=='BE' for r in records)!=4:raise ValueError('Ungültige Bundeslandverteilung.')
    expiries=[]
    for r in records:
        age=today.year-r['birth_date'].year-((today.month,today.day)<(r['birth_date'].month,r['birth_date'].day))
        if not 28<=age<=64 or not max(date(1995,1,1),year_shift(r['birth_date'],18))<=r['entry_date']<=today:raise ValueError('Ungültiges Geburts-/Beitrittsdatum.')
        if r['weekly_minutes']!=2400 or r['vacation_days']!=30 or r['email']!=EMAIL:raise ValueError('Ungültige Arbeitszeit-/Kontaktdaten.')
        if r['bahncard']:
            span=(r['bahncard_valid_until']-today).days
            if not 120<=span<=365:raise ValueError('Ungültige BahnCard-Gültigkeit.')
            expiries.append(r['bahncard_valid_until'])
        elif r['bahncard_valid_until'] is not None:raise ValueError('Gültigkeit ohne BahnCard.')
    if len(set(expiries))!=19:raise ValueError('BahnCard-Gültigkeiten müssen unterschiedlich sein.')


def delete_tf_records(db):
    """Delete the FK closure of TF users, in child-before-parent order.

    Includes plans, entries, receipts, changes, sessions, photos, mailbox credentials,
    draft/actor references and companion tables. Staff/admin records stay intact.
    Foreign-key checks remain enabled; no TRUNCATE or foreign-key disabling.
    """
    ids=set(db.scalars(select(User.id).where(User.role=='tf').with_for_update()))
    if not ids:return {}
    tables=Base.metadata.sorted_tables
    columns={('users','id'):ids}
    predicates={'users':User.__table__.c.id.in_(ids)}
    for table in tables:
        if table.name=='users':continue
        filters=[fk.parent.in_(columns[(fk.column.table.name,fk.column.name)])
                 for fk in table.foreign_keys if columns.get((fk.column.table.name,fk.column.name))]
        if not filters:continue
        predicate=or_(*filters)
        keys=list(table.primary_key.columns)
        rows=db.execute(select(*keys).where(predicate)).all()
        if not rows:continue
        for offset,key in enumerate(keys):columns[(table.name,key.name)]={r[offset] for r in rows}
        # Capture FK filters while the parent IDs are still available.
        predicates[table.name]=predicate
    deleted={}
    for table in reversed(tables):
        if table.name in predicates:
            result=db.execute(delete(table).where(predicates[table.name]))
            deleted[table.name]=result.rowcount
    db.expire_all()
    return deleted


def replace_all_tf(db,today=None,seed=None):
    """Caller owns commit/rollback. Validate photos and all rows before deleting."""
    today=today or berlin_today()
    from ..user_directories import storage_root
    folder=storage_root()/'TF'
    if folder.is_symlink():raise ValueError('Ungültiger TF-Verzeichnisroot')
    reserved=list(db.scalars(select(User.username)))
    if folder.is_dir():reserved.extend(p.name for p in folder.iterdir())
    records=build_records(today,seed,reserved)
    validate_records(records,today)
    photos=[]
    for record in records:
        path=DATA/record['photo']
        if not path.is_file():raise ValueError(f'Fiktives Profilbild fehlt: {record["photo"]}')
        photos.append(normalize(path.read_bytes()))
    # Preserve unique user identities even on SQLite (which can reuse deleted IDs).
    next_id=(db.scalar(select(func.max(User.id))) or 0)+1
    deleted=delete_tf_records(db)
    for index,(record,photo) in enumerate(zip(records,photos)):
        user=User(id=next_id+index,username=record['username'],password_hash=hash_password(PASSWORD),role='tf',active=True)
        db.add(user);db.flush()
        db.add(AccountPolicy(user_id=user.id,must_change_password=True))
        db.add(TfProfile(user_id=user.id,first_name=record['first_name'],last_name=record['last_name'],
            personnel_number=record['personnel_number'],target_hours_minutes=0,vacation_days=30,
            birth_date=record['birth_date'],bahncard=record['bahncard'],gender=record['gender'],email=EMAIL,federal_state=record['federal_state']))
        db.add(TfEmployment(user_id=user.id,tf_number=record['tf_number'],weekly_minutes=2400,
            entry_date=record['entry_date'],exit_date=None,immediate_block=False,nationality='DE'))
        db.add(TfIdentity(user_id=user.id,gender=record['gender']))
        db.add(TfDutyProfile(user_id=user.id,driver_type=record['driver_type']))
        for a in record['addresses']:db.add(TfAddress(user_id=user.id,**a))
        if record['bahncard']:db.add(TfBahnCardValidity(user_id=user.id,valid_until=record['bahncard_valid_until']))
        db.add(ProfilePhoto(user_id=user.id,image_data=photo));db.flush()
        db.get(TfProfile,user.id).target_hours_minutes=monthly_minutes(db,user.id,today.year,today.month)
    db.flush()
    from ..user_directories import sync_user_directories
    sync_user_directories(db)
    return dict(deleted=deleted,created=20,people=[{k:v for k,v in row.items() if k!='photo'} for row in records])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace-all-tf',action='store_true',help='Alle TF und abhängige Daten in einer Transaktion ersetzen.')
    parser.add_argument('--seed',type=int,help='Optionaler reproduzierbarer Zufalls-Seed.')
    args=parser.parse_args()
    if not args.replace_all_tf:
        records=build_records(seed=args.seed);validate_records(records,berlin_today())
        print(json.dumps({'preview':True,'people':records},ensure_ascii=False,default=str,indent=2));return
    # Production uses MySQL/InnoDB; all new tables must exist before the transaction.
    Base.metadata.create_all(engine())
    from .tf_profiles import ensure_gender_column
    with Session(engine()) as db:
        ensure_gender_column(db);db.commit()
    with Session(engine()) as db:
        try:
            result=replace_all_tf(db,seed=args.seed)
            db.commit()
        except Exception:
            db.rollback();raise
    print(json.dumps(result,ensure_ascii=False,default=str,indent=2))


if __name__=='__main__':main()
