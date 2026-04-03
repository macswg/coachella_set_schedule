from datetime import datetime, time, timedelta
from typing import Optional
from pydantic import BaseModel, computed_field


class Act(BaseModel):
    """Represents a single act in the festival schedule."""

    act_name: str
    scheduled_start: time
    scheduled_end: Optional[time] = None
    actual_start: Optional[time] = None
    actual_end: Optional[time] = None
    notes: Optional[str] = None
    screentime_total_seconds: int = 0
    screentime_session_start: Optional[time] = None

    @computed_field
    @property
    def is_loadin(self) -> bool:
        """Returns True if this is a load-in row (informational only, no buttons)."""
        return 'load in' in self.act_name.lower()

    @computed_field
    @property
    def is_ondeck(self) -> bool:
        """Returns True if this is an on-deck row (screentime buttons only)."""
        return 'on deck' in self.act_name.lower() or 'stage time' in self.act_name.lower()

    @staticmethod
    def _duration_seconds(start: time, end: time) -> int:
        """Elapsed seconds from start to end, handling midnight crossover."""
        start_dt = datetime.combine(datetime.today(), start)
        end_dt = datetime.combine(datetime.today(), end)
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        return int((end_dt - start_dt).total_seconds())

    @staticmethod
    def _variance_seconds(scheduled: time, actual: time) -> int:
        """Signed seconds between scheduled and actual time (positive = late),
        handling midnight crossover."""
        scheduled_dt = datetime.combine(datetime.today(), scheduled)
        actual_dt = datetime.combine(datetime.today(), actual)
        if actual_dt < scheduled_dt - timedelta(hours=12):
            actual_dt += timedelta(days=1)
        return int((actual_dt - scheduled_dt).total_seconds())

    @computed_field
    @property
    def scheduled_duration(self) -> int:
        """Scheduled duration in seconds."""
        if self.scheduled_end is None:
            return 0
        return self._duration_seconds(self.scheduled_start, self.scheduled_end)

    @computed_field
    @property
    def actual_duration(self) -> Optional[int]:
        """Actual duration in seconds, if both start and end are recorded."""
        if self.actual_start and self.actual_end:
            return self._duration_seconds(self.actual_start, self.actual_end)
        return None

    @computed_field
    @property
    def start_variance(self) -> Optional[int]:
        """Variance in seconds from scheduled start (positive = late)."""
        if self.actual_start:
            return self._variance_seconds(self.scheduled_start, self.actual_start)
        return None

    @computed_field
    @property
    def end_variance(self) -> Optional[int]:
        """Variance in seconds from scheduled end (positive = late)."""
        if self.actual_end and self.scheduled_end:
            return self._variance_seconds(self.scheduled_end, self.actual_end)
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
