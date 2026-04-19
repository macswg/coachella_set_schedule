from __future__ import annotations

from datetime import datetime, time
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.engine import Base


class Show(Base):
    __tablename__ = "shows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_previous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    acts: Mapped[list["Act"]] = relationship(
        back_populates="show",
        cascade="all, delete-orphan",
        order_by="Act.row_index",
    )


class Act(Base):
    __tablename__ = "acts"
    __table_args__ = (UniqueConstraint("show_id", "row_index", name="uq_act_show_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id", ondelete="CASCADE"), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    act_name: Mapped[str] = mapped_column(String, nullable=False)
    scheduled_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    scheduled_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    actual_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    actual_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    screentime_total_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    screentime_session_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    show: Mapped[Show] = relationship(back_populates="acts")


class RecordingEvent(Base):
    __tablename__ = "recording_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id", ondelete="CASCADE"), nullable=False)
    act_id: Mapped[Optional[int]] = mapped_column(ForeignKey("acts.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    fired_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
