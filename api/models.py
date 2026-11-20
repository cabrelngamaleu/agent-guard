from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(200))
    payload: Mapped[str] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))

class ActionRequest(Base):
    __tablename__ = "action_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40))
    agent: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(200))
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(300))
    decided_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_at: Mapped[str | None] = mapped_column(String(40), nullable=True)