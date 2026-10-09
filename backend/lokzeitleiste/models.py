from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGBLOB
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
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    federal_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
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


class ReportDispatch(Base):
    __tablename__ = "report_dispatches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    work_month_id: Mapped[int] = mapped_column(ForeignKey("work_months.id"), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    filename: Mapped[str] = mapped_column(String(120), nullable=False)
    pdf_data: Mapped[bytes | None] = mapped_column(LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PlanMonth(Base):
    __tablename__ = "plan_months"
    __table_args__ = (UniqueConstraint("tf_user_id", "year", "month"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    days: Mapped[list["PlanDay"]] = relationship(back_populates="period", cascade="all, delete-orphan")


class PlanDay(Base):
    __tablename__ = "plan_days"
    __table_args__ = (UniqueConstraint("plan_month_id", "day"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_month_id: Mapped[int] = mapped_column(ForeignKey("plan_months.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    period: Mapped[PlanMonth] = relationship(back_populates="days")


class PlanChange(Base):
    __tablename__ = "plan_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    previous_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    new_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_note: Mapped[str] = mapped_column(String(500), nullable=False)
    new_note: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(12), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)


class WorkTimeChange(Base):
    __tablename__ = "work_time_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("work_entries.id"), nullable=False, index=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    previous_start: Mapped[str] = mapped_column(String(5), nullable=False)
    previous_end: Mapped[str] = mapped_column(String(5), nullable=False)
    new_start: Mapped[str] = mapped_column(String(5), nullable=False)
    new_end: Mapped[str] = mapped_column(String(5), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AccountPolicy(Base):
    __tablename__ = "account_policies"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StaffProfile(Base):
    __tablename__ = "staff_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    nationality: Mapped[str] = mapped_column(String(120), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    cost_center: Mapped[str] = mapped_column(String(80), nullable=False)


class StaffAddress(Base):
    __tablename__ = "staff_addresses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("staff_profiles.user_id"), nullable=False, index=True)
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    house_number: Mapped[str] = mapped_column(String(30), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)


class ModulePermission(Base):
    __tablename__ = "module_permissions"
    __table_args__ = (UniqueConstraint("user_id", "module"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(40), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)


class AccountAudit(Base):
    __tablename__ = "account_audits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
