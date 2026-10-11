"""Replace TF accounts and their dependent records with fictional development data."""
import argparse
import random
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime

from sqlalchemy import delete, select, or_
from sqlalchemy.orm import Session

from .db import engine
from .models import Base, TfProfile, User, TfEmployment, TfDutyProfile, TfBahnCardValidity, AccountPolicy, TfAddress
from .accounts.tf_profiles import monthly_minutes
from .security import hash_password


NAMES = [
    ('Thomas', 'Adler'), ('Michael', 'Bergmann'), ('Stefan', 'Conrad'),
    ('Andreas', 'Dorn'), ('Markus', 'Ebert'), ('Daniel', 'Falk'),
    ('Christian', 'Gärtner'), ('Sebastian', 'Hartmann'), ('Florian', 'Jansen'),
    ('Martin', 'Keller'), ('Tobias', 'Lindner'), ('Jan', 'Mertens'),
    ('Patrick', 'Neumann'), ('Oliver', 'Peters'), ('Anna', 'Richter'),
    ('Julia', 'Sommer'), ('Katharina', 'Vogel'), ('Laura', 'Winter'),
    ('Alex', 'Wolff'), ('Robin', 'Ziegler'),
]


def replace_tf(db, today):
    db.flush()
    # Derive dependent rows from all foreign keys, including planning/mail/audit tables.
    conditions = {User.__table__: User.__table__.c.role == 'tf'}
    for table in Base.metadata.sorted_tables:
        if table is User.__table__:
            continue
        terms = []
        for fk in table.foreign_keys:
            parent = fk.column.table
            if parent in conditions:
                terms.append(fk.parent.in_(select(fk.column).where(conditions[parent])))
        if terms:
            conditions[table] = or_(*terms)
    for table in reversed(Base.metadata.sorted_tables):
        if table in conditions:
            db.execute(delete(table).where(conditions[table]))
    # Core deletes bypass ORM state; clear stale identities before reusing IDs.
    db.expunge_all()
    rng = random.Random(787)
    validity = rng.sample(range(120, 366), 19)
    earliest = date(1995, 1, 1)
    for index, (first, last) in enumerate(NAMES):
        number = str(787001 + index)
        user = User(username=number, password_hash=hash_password('tomcom123456'), role='tf')
        db.add(user)
        db.flush()
        db.add(TfProfile(
            user_id=user.id, first_name=first, last_name=last, personnel_number=number,
            gender='männlich' if index < 14 else 'weiblich' if index < 18 else 'divers' if index == 18 else 'keine Angabe',
            target_hours_minutes=0, vacation_days=30,
            birth_date=date(1970 + index, 1 + index % 12, 1 + index % 27),
            bahncard=100 if index < 18 else 50 if index == 18 else 0,
            email=f'tf{number}@example.com', federal_state='BE',
        ))
        db.add(TfEmployment(user_id=user.id, tf_number=int(number), weekly_minutes=2400,
                            entry_date=earliest + timedelta(days=rng.randint(0, (today-earliest).days)),
                            immediate_block=False, nationality='DE'))
        db.add(TfDutyProfile(user_id=user.id, driver_type='border' if index < 3 else 'both' if index < 5 else 'route'))
        db.add(AccountPolicy(user_id=user.id, must_change_password=False))
        db.add(TfAddress(user_id=user.id, street='Musterstraße', house_number=str(index+1),
                         postal_code='10115', city='Berlin', federal_state='BE', is_postal=True))
        if index < 19:
            db.add(TfBahnCardValidity(user_id=user.id, valid_until=today + timedelta(days=validity[index])))
    db.flush()
    for user in db.scalars(select(User).where(User.role == 'tf')):
        db.get(TfProfile, user.id).target_hours_minutes = monthly_minutes(db, user.id, today.year, today.month)
    db.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace-all-tf', action='store_true', required=True,
                        help='Explicitly delete all TF accounts, sessions, months, entries and dispatches; admins remain.')
    parser.parse_args()
    with Session(engine()) as db, db.begin():
        replace_tf(db, datetime.now(ZoneInfo('Europe/Berlin')).date())
    print('20 fiktive TF angelegt; bisherige TF und zugehörige Datensätze gelöscht.')


if __name__ == '__main__':
    main()
