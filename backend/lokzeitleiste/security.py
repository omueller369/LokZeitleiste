import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SessionToken, User, AccountLoginStamp, now_utc


ITERATIONS = 600_000
TOKEN_LIFETIME = timedelta(days=365)


def hash_password(password: str) -> str:
    if len(password) < 6:
        raise ValueError("Passwort muss mindestens 6 Zeichen haben")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        method, count, salt, digest = stored.split("$")
        if method != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(count))
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def issue_token(session: Session, user: User) -> str:
    stamp=session.get(AccountLoginStamp,user.id)
    if stamp:stamp.previous_login_at=stamp.last_login_at;stamp.last_login_at=now_utc()
    else:session.add(AccountLoginStamp(user_id=user.id,last_login_at=now_utc()))
    token = secrets.token_urlsafe(32)
    session.add(SessionToken(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                             expires_at=now_utc() + TOKEN_LIFETIME))
    session.commit()
    return token


def user_from_token(session: Session, raw: str | None) -> User | None:
    if not raw:
        return None
    digest = hashlib.sha256(raw.encode()).hexdigest()
    token = session.scalar(select(SessionToken).where(SessionToken.token_hash == digest))
    if not token or token.expires_at <= now_utc():
        return None
    user = session.get(User, token.user_id)
    return user if user and account_active(session, user) else None


def revoke_token(session: Session, raw: str):
    digest = hashlib.sha256(raw.encode()).hexdigest()
    token = session.scalar(select(SessionToken).where(SessionToken.token_hash == digest))
    if token:
        session.delete(token)
        session.commit()


def account_active(session, user):
    if not user.active: return False
    if user.role != 'tf': return True
    from .accounts.tf_profiles import berlin_today
    from .models import TfEmployment
    employment = session.get(TfEmployment, user.id)
    return not employment or (not employment.immediate_block and
        (employment.exit_date is None or employment.exit_date > berlin_today()))
