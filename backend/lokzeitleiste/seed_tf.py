"""Replace TF accounts and their dependent records with fictional development data."""
import argparse
import random
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .db import engine
from .models import ReportDispatch, SessionToken, TfProfile, User, WorkEntry, WorkMonth
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
    ids = select(User.id).where(User.role == 'tf')
    months = select(WorkMonth.id).where(WorkMonth.tf_user_id.in_(ids))
    db.execute(delete(ReportDispatch).where(ReportDispatch.tf_user_id.in_(ids)))
    db.execute(delete(WorkEntry).where(WorkEntry.work_month_id.in_(months)))
    db.execute(delete(WorkMonth).where(WorkMonth.tf_user_id.in_(ids)))
    db.execute(delete(SessionToken).where(SessionToken.user_id.in_(ids)))
    db.execute(delete(TfProfile).where(TfProfile.user_id.in_(ids)))
    db.execute(delete(User).where(User.role == 'tf'))
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
            qualification='Grenz-TF' if index < 3 else 'Grenz- und Strecken-TF' if index < 5 else 'Strecken-TF',
            weekly_hours_minutes=2400, target_hours_minutes=10400, vacation_days=30,
            birth_date=date(1970 + index, 1 + index % 12, 1 + index % 27),
            joined_on=earliest + timedelta(days=rng.randint(0, (today-earliest).days)),
            bahncard=100 if index < 18 else 50 if index == 18 else 0,
            bahncard_valid_until=today + timedelta(days=validity[index]) if index < 19 else None,
            photo_placeholder='Bild folgt', email=f'tf{number}@example.com', federal_state='BE',
        ))
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
