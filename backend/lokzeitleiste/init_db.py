import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, engine
from .user_directories import sync_user_directories, directory_transaction
from .models import User
from .security import hash_password


def main():
    Base.metadata.create_all(engine())
    from .accounts.tf_profiles import migrate_existing, seed_stations, migrate_legacy_gender, ensure_gender_column
    with Session(engine()) as db:
        from .app_defaults import ensure_defaults
        ensure_defaults(db)
        from .leasing import seed_and_migrate
        seed_and_migrate(db)
        ensure_gender_column(db)
        migrate_existing(db)
        migrate_legacy_gender(db)
        seed_stations(db)
        from .planning.clear_legacy_notes import migrate as clear_old_notes
        clear_old_notes(db)
        db.commit()
        sync_user_directories(db)
        from .documents.archive import backfill_documents
        backfill_documents(db)
        db.commit()
    if len(sys.argv) == 2 and sys.argv[1] == "--create-admin":
        name = input("Admin-Benutzername: ").strip().lower()
        if not 3 <= len(name) <= 64 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for c in name):
            raise SystemExit("Ungültiger Benutzername")
        password = getpass.getpass("Admin-Passwort (mindestens 6 Zeichen): ")
        with Session(engine()) as db:
            if db.scalar(select(User).where(User.username == name)):
                raise SystemExit("Benutzername bereits vorhanden")
            user=User(username=name, password_hash=hash_password(password), role="admin")
            db.add(user)
            with directory_transaction(user,creating=True):
                db.commit()
        print("Admin angelegt.")
    else:
        print("Datenbanktabellen angelegt.")


if __name__ == "__main__":
    main()
