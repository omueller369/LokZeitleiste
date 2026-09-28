import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import engine
from ..models import ReportDispatch, now_utc
from .mailer import send_receipt


log = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


def process_dispatch(dispatch_id: int):
    with Session(engine()) as session:
        dispatch = session.scalar(select(ReportDispatch).where(ReportDispatch.id == dispatch_id).with_for_update())
        if not dispatch or dispatch.status == "sent" or dispatch.attempts >= MAX_ATTEMPTS:
            return
        try:
            if not dispatch.pdf_data:
                raise RuntimeError("PDF-Daten fehlen")
            send_receipt(recipient=dispatch.recipient_email, filename=dispatch.filename,
                         pdf_data=dispatch.pdf_data)
        except Exception as exc:
            dispatch.status = "failed"
            dispatch.attempts += 1
            dispatch.last_error = str(exc)[:500]
            log.exception("PDF-Versand fehlgeschlagen, Versand-ID %s", dispatch_id)
        else:
            dispatch.status = "sent"
            dispatch.attempts += 1
            dispatch.sent_at = now_utc()
            dispatch.pdf_data = None
            dispatch.last_error = ""
        session.commit()
