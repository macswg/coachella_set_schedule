from datetime import datetime, time, timedelta
from typing import Optional
from pydantic import BaseModel, computed_field


class Act(BaseModel):
    """Represents a single act in the festival schedule."""

    act_name: str
    scheduled_start: time
    scheduled_end: time
    actual_start: Optional[time] = None
    actual_end: Optional[time] = None
    notes: Optional[str] = None

    @computed_field
    @property
    def scheduled_duration(self) -> int:
        """Scheduled duration in seconds."""
        start_dt = datetime.combine(datetime.today(), self.scheduled_start)
        end_dt = datetime.combine(datetime.today(), self.scheduled_end)
        return int((end_dt - start_dt).total_seconds())

    @computed_field
    @property
    def actual_duration(self) -> Optional[int]:
        """Actual duration in seconds, if both start and end are recorded."""
        if self.actual_start and self.actual_end:
            start_dt = datetime.combine(datetime.today(), self.actual_start)
            end_dt = datetime.combine(datetime.today(), self.actual_end)
            return int((end_dt - start_dt).total_seconds())
        return None

    @computed_field
    @property
    def start_variance(self) -> Optional[int]:
        """Variance in seconds from scheduled start (positive = late)."""
        if self.actual_start:
            scheduled_dt = datetime.combine(datetime.today(), self.scheduled_start)
            actual_dt = datetime.combine(datetime.today(), self.actual_start)
            return int((actual_dt - scheduled_dt).total_seconds())
        return None

    @computed_field
    @property
    def end_variance(self) -> Optional[int]:
        """Variance in seconds from scheduled end (positive = late)."""
        if self.actual_end:
            scheduled_dt = datetime.combine(datetime.today(), self.scheduled_end)
            actual_dt = datetime.combine(datetime.today(), self.actual_end)
            return int((actual_dt - scheduled_dt).total_seconds())
        return None

    def is_complete(self) -> bool:
        """Returns True if the act has both start and end times recorded."""
        return self.actual_start is not None and self.actual_end is not None

    def is_in_progress(self) -> bool:
        """Returns True if the act has started but not ended."""
        return self.actual_start is not None and self.actual_end is None

    def is_pending(self) -> bool:
        """Returns True if the act hasn't started yet."""
        return self.actual_start is None


class Schedule(BaseModel):
    """Represents the full schedule for a stage."""

    stage_name: str
    acts: list[Act]
