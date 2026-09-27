from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(8), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    profile: Mapped["TfProfile | None"] = relationship(back_populates="user", uselist=False)


class TfProfile(Base):
    __tablename__ = "tf_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    personnel_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    target_hours_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    vacation_days: Mapped[int] = mapped_column(Integer, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    bahncard: Mapped[int] = mapped_column(Integer, nullable=False)
    user: Mapped[User] = relationship(back_populates="profile")


class SessionToken(Base):
    __tablename__ = "session_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class WorkMonth(Base):
    __tablename__ = "work_months"
    __table_args__ = (UniqueConstraint("tf_user_id", "year", "month"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    entries: Mapped[list["WorkEntry"]] = relationship(back_populates="work_month", cascade="all, delete-orphan")


class WorkEntry(Base):
    __tablename__ = "work_entries"
    __table_args__ = (UniqueConstraint("work_month_id", "client_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_month_id: Mapped[int] = mapped_column(ForeignKey("work_months.id"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    pause_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    guest_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    away: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accommodation: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    hotel_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc, nullable=False)
    work_month: Mapped[WorkMonth] = relationship(back_populates="entries")
