import hashlib,io,logging,os,warnings
from email.message import EmailMessage
from pathlib import PurePosixPath
from PIL import Image
from pypdf import PdfReader
from pydantic import TypeAdapter,EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import engine
from ..models import DutyReceipt,DutyReport,User,now_utc
from ..reports.mailer import _send_message,smtp_configured
from ..reports.service import MAX_ATTEMPTS
from ..i18n import translate,user_language

MAX_FILE=10*1024*1024
log=logging.getLogger(__name__)


def recipient():
    value=os.getenv('WORK_REPORT_RECEIPT_EMAIL','').strip()
    try:return str(TypeAdapter(EmailStr).validate_python(value)) if value else ''
    except ValueError:return ''


def validate_receipt(filename,content):
    if not content or len(content)>MAX_FILE:raise ValueError('Beleg darf höchstens 10 MB groß sein.')
    name=PurePosixPath((filename or 'Beleg').replace('\\','/')).name
    if any(ord(c)<32 or ord(c)==127 for c in name) or len(name)>120:raise ValueError('Ungültiger Belegdateiname.')
    suffix=PurePosixPath(name).suffix.lower()
    if suffix=='.pdf':
        if not content.startswith(b'%PDF-'):raise ValueError('Ungültiger PDF-Beleg.')
        try:
            pdf=PdfReader(io.BytesIO(content),strict=True)
            if pdf.is_encrypted or not 1<=len(pdf.pages)<=100:raise ValueError('PDF muss unverschlüsselt sein und 1–100 Seiten enthalten.')
        except Exception as exc:raise ValueError('Ungültiger oder verschlüsselter PDF-Beleg.') from exc
        mime='application/pdf'
    elif suffix in ('.jpg','.jpeg','.png'):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as image:
                    expected='PNG' if suffix=='.png' else 'JPEG'
                    if image.format!=expected or image.width*image.height>25_000_000 or getattr(image,'n_frames',1)!=1:raise ValueError('Ungültiger Bildbeleg.')
                    image.verify()
        except Exception as exc:raise ValueError('Ungültiger Bildbeleg.') from exc
        mime='image/png' if suffix=='.png' else 'image/jpeg'
    else:raise ValueError('Bitte PDF, JPEG oder PNG als Beleg wählen.')
    return name,mime,hashlib.sha256(content).hexdigest()


def receipt_view(row):
    return dict(id=row.id,filename=row.filename,status=row.status,attempts=row.attempts,
                sent_at=row.sent_at.isoformat() if row.sent_at else None)


def process_receipt(receipt_id):
    with Session(engine()) as db:
        row=db.scalar(select(DutyReceipt).where(DutyReceipt.id==receipt_id).with_for_update())
        if not row or row.status=='sent' or row.attempts>=MAX_ATTEMPTS:return
        if not smtp_configured() or not (row.recipient_email or recipient()):return
        report=db.get(DutyReport,row.report_id)
        if not report:return
        if not row.recipient_email:row.recipient_email=recipient()
        try:
            user=db.get(User,report.tf_user_id)
            message=EmailMessage()
            message['To']=row.recipient_email
            t=lambda text:translate(text,user_language(db,user.id))
            message['Subject']=t('LokZeitleiste: Quittungsbeleg zum Arbeitsbericht')
            message.set_content(f"{t('TF-Nummer')}: {user.username}\n{t('Arbeitsbericht')}: {report.id}\n{t('Quittungsbeleg')}: {row.filename}\n")
            main,sub=row.mime_type.split('/')
            message.add_attachment(row.content,maintype=main,subtype=sub,filename=row.filename)
            message['Message-ID']=f'<duty-receipt-{row.id}-{row.content_hash[:16]}@lokzeitleiste.local>'
            _send_message(message)
        except Exception:
            row.status='failed';row.attempts+=1;row.last_error='Belegversand fehlgeschlagen'
            log.exception('Belegversand fehlgeschlagen, Beleg-ID %s',row.id)
        else:
            row.status='sent';row.attempts+=1;row.sent_at=now_utc();row.last_error=''
        db.commit()
