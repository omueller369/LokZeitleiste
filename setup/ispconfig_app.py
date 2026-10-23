"""Application-side setup checks, executed with the application's virtualenv/user."""
import json
import sys
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from lokzeitleiste.db import engine


def main():
    mode=sys.argv[1]
    if mode=='empty':
        try:
            with engine().connect() as connection:
                schema=inspect(connection)
                if schema.get_table_names() or schema.get_view_names():
                    raise SystemExit('Datenbank ist nicht leer. Neuinstallation abgebrochen; keine Tabellen verändert.')
        except SystemExit:raise
        except Exception as exc:raise SystemExit('Datenbankverbindung fehlgeschlagen ('+type(exc).__name__+'). Zugang/Host und Rechte in ISPConfig prüfen.') from None
        print('Vorhandene ISPConfig-Datenbank verbunden und leer.')
    elif mode=='verify':
        from sqlalchemy import select,func
        from lokzeitleiste.models import User,ProfilePhoto
        with Session(engine()) as db:
            drivers=db.scalar(select(func.count()).select_from(User).where(User.role=='tf'))
            photos=db.scalar(select(func.count()).select_from(ProfilePhoto).join(User,User.id==ProfilePhoto.user_id).where(User.role=='tf'))
            if drivers!=20 or photos!=20:raise SystemExit('Testdatenprüfung fehlgeschlagen: 20 TF mit Bildern erwartet.')
            print(json.dumps({'tf':drivers,'fotos':photos}))
    else:raise SystemExit('Unbekannter Prüfmodus')

if __name__=='__main__':main()
