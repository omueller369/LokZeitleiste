import argparse
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import engine
from ..models import ReportDispatch
from .service import MAX_ATTEMPTS, process_dispatch


def poll_once():
    with Session(engine()) as db:
        ids = db.scalars(select(ReportDispatch.id)
                         .where(ReportDispatch.status.in_(("pending", "failed")),
                                ReportDispatch.attempts < MAX_ATTEMPTS)
                         .order_by(ReportDispatch.id).limit(20)).all()
    for dispatch_id in ids:
        process_dispatch(dispatch_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if args.interval < 5:
        parser.error("Intervall muss mindestens 5 Sekunden betragen")
    while True:
        poll_once()
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
