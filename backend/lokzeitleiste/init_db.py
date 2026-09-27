import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, engine
from .models import User
from .security import hash_password


def main():
    Base.metadata.create_all(engine())
    if len(sys.argv) == 2 and sys.argv[1] == "--create-admin":
        name = input("Admin-Benutzername: ").strip().lower()
        if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for c in name):
            raise SystemExit("Ungültiger Benutzername")
        password = getpass.getpass("Admin-Passwort (mindestens 12 Zeichen): ")
        with Session(engine()) as db:
            if db.scalar(select(User).where(User.username == name)):
                raise SystemExit("Benutzername bereits vorhanden")
            db.add(User(username=name, password_hash=hash_password(password), role="admin"))
            db.commit()
        print("Admin angelegt.")
    else:
        print("Datenbanktabellen angelegt.")


if __name__ == "__main__":
    main()
