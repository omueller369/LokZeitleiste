import os
import smtplib
import ssl
from email.message import EmailMessage


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM")
                and os.getenv("SMTP_SECURITY", "ssl") in ("ssl", "starttls"))


def send_receipt(*, recipient: str, filename: str, pdf_data: bytes):
    if not smtp_configured():
        raise RuntimeError("SMTP_HOST, SMTP_FROM und SMTP_SECURITY müssen gesetzt sein")
    host = os.environ["SMTP_HOST"]
    security = os.getenv("SMTP_SECURITY", "ssl")
    port = int(os.getenv("SMTP_PORT", "465" if security == "ssl" else "587"))
    sender = os.environ["SMTP_FROM"]
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = "LokZeitleiste: Eingang Ihrer Arbeitszeiten"
    message.set_content(
        "Anbei erhalten Sie die tabellarische Bestätigung der übermittelten Tagesdaten. "
        "Dies ist keine Entgelt- oder Tarifabrechnung."
    )
    message.add_attachment(pdf_data, maintype="application", subtype="pdf", filename=filename)
    context = ssl.create_default_context()
    if security == "ssl":
        connection = smtplib.SMTP_SSL(host, port, timeout=20, context=context)
    else:
        connection = smtplib.SMTP(host, port, timeout=20)
    with connection as smtp:
        if security == "starttls":
            smtp.starttls(context=context)
        username = os.getenv("SMTP_USERNAME")
        password = os.getenv("SMTP_PASSWORD")
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)
