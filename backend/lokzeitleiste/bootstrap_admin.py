"""Admin aus einer geschützten Passwortdatei (stdin) anlegen; keine Passwortausgabe."""
import re
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import engine
from .models import User
from .security import hash_password


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z0-9._-]{3,64}", sys.argv[1]):
        raise SystemExit("Admin-Benutzername ungültig")
    username = sys.argv[1]
    password = sys.stdin.read(4097).rstrip("\r\n")
    if not 12 <= len(password) <= 4096 or "\n" in password or "\r" in password:
        raise SystemExit("Passwortdatei: genau eine Zeile mit 12 bis 4096 Zeichen erforderlich")
    with Session(engine()) as db:
        existing = db.scalar(select(User).where(User.username == username))
        if existing:
            if existing.role != "admin" or not existing.active:
                raise SystemExit("Benutzername gehört keinem aktiven Admin; keine Änderung durchgeführt")
            print("Aktiver Admin bereits vorhanden; Passwort bleibt unverändert.")
            return
        db.add(User(username=username, password_hash=hash_password(password), role="admin"))
        db.commit()
    print("Admin angelegt.")


if __name__ == "__main__":
    main()
