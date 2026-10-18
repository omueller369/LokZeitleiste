"""Validated host-provisioning manifest; no credentials or document contents."""
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import engine
from ..models import User
from ..user_directories import component,ROLE_DIRECTORIES,sync_user_directories


def main():
    with Session(engine()) as db:
        sync_user_directories(db)
        print(json.dumps([dict(id=u.id,username=component(u.username),category=ROLE_DIRECTORIES[u.role])
            for u in db.scalars(select(User).where(User.role.in_(ROLE_DIRECTORIES)))],ensure_ascii=False))


if __name__=='__main__':main()
