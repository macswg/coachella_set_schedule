"""
Google Sheets integration for persistent storage.

This module provides the same interface as store.py but reads/writes
to Google Sheets instead of in-memory storage.

To use:
1. Create a Google Cloud project and enable the Sheets API
2. Create a service account and download the JSON key
3. Share your spreadsheet with the service account email
4. Set GOOGLE_SHEETS_ID and GOOGLE_SERVICE_ACCOUNT_FILE in .env
"""

from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

from app.config import settings
from app.models import time_to_secs
from app.models import Act

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# Column indices (1-based for gspread)
COL_ARTIST_NAME = 3      # C - "artist name"
COL_SCHEDULED_START = 4  # D - "scheduled start"
COL_SCHEDULED_END = 5    # E - "scheduled end"
COL_ACTUAL_START = 6     # F - "actual time on"
COL_ACTUAL_END = 7       # G - "actual time off"
COL_SCREENTIME_TOTAL = 8  # H - "screentime total seconds"

HEADER_ROW = 5  # Header is on row 5, data starts row 6

_client: Optional[gspread.Client] = None
_sheet: Optional[gspread.Worksheet] = None

# Multi-show state: ordered list of tabs and current position
_show_tabs: list[str] = settings.SHOW_TABS if settings.SHOW_TABS else ([settings.GOOGLE_SHEET_TAB] if settings.GOOGLE_SHEET_TAB else [])
# Start at the tab named by GOOGLE_SHEET_TAB if it's in the list; otherwise index 0
_active_tab_index: int = (
    _show_tabs.index(settings.GOOGLE_SHEET_TAB)
    if settings.GOOGLE_SHEET_TAB and settings.GOOGLE_SHEET_TAB in _show_tabs
    else 0
)

# Row number cache: act_name → 1-indexed sheet row. Rebuilt on every get_schedule() call.
_row_cache: dict[str, int] = {}

# In-memory screentime tracking (survives schedule list rebuilds)
_screentime_sessions: dict[str, time] = {}
_screentime_totals: dict[str, int] = {}  # Cache new totals so post-write reads aren't stale


def _get_sheet() -> gspread.Worksheet:
    """Get or create the Google Sheets client and worksheet."""
    global _client, _sheet

    if _sheet is None:
        creds = Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=SCOPES,
        )
        _client = gspread.authorize(creds)
        spreadsheet = _client.open_by_key(settings.GOOGLE_SHEETS_ID)
        active_tab = _show_tabs[_active_tab_index] if _show_tabs else None
        if active_tab:
            _sheet = spreadsheet.worksheet(active_tab)
        else:
            _sheet = spreadsheet.sheet1

    return _sheet


def _parse_time(time_str: str) -> Optional[time]:
    """Parse a time string to a time object. Handles HH:MM, HH:MM:SS, and H:MM AM/PM formats."""
    if not time_str or time_str.strip() == "":
        return None
    time_str = time_str.strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    return None


def _format_time(t: Optional[time]) -> str:
    """Format a time object to HH:MM string."""
    if t is None:
        return ""
    return t.strftime("%H:%M")


def _get_cell(row: list, col: int) -> str:
    """Safely get a cell value from a row (col is 1-indexed)."""
    idx = col - 1
    if idx < len(row):
        return str(row[idx])
    return ""


def _format_screentime(seconds: int) -> str:
    """Format seconds as H:MM:SS for storage in Google Sheets."""
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}:{mins:02d}:{secs:02d}"




def _parse_screentime_seconds(value: str) -> int:
    """Parse screentime value which may be an integer, MM:SS, or HH:MM:SS."""
    value = value.strip()
    if not value:
        return 0
    if ":" in value:
        parts = value.split(":")
        try:
            if len(parts) == 2:
                minutes, seconds = parts
                return int(minutes) * 60 + int(seconds)
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            return 0
        except (ValueError, IndexError):
            return 0
    try:
        return int(value)
    except ValueError:
        return 0


def get_schedule() -> list[Act]:
    """Fetch all acts from the Google Sheet."""
    global _row_cache
    sheet = _get_sheet()
    # Get all values starting from the data row (after header)
    all_values = sheet.get_all_values()
    data_rows = all_values[HEADER_ROW:]  # Skip header rows (0-indexed, so row 6 = index 5)

    # Rebuild row number cache from this read
    _row_cache = {
        _get_cell(row, COL_ARTIST_NAME): i + HEADER_ROW + 1
        for i, row in enumerate(data_rows)
        if _get_cell(row, COL_ARTIST_NAME)
    }

    acts = []
    last_scheduled_end: Optional[time] = None  # used to infer END OF SHOW time when blank
    for row in data_rows:
        act_name = _get_cell(row, COL_ARTIST_NAME)
        scheduled_start = _parse_time(_get_cell(row, COL_SCHEDULED_START))
        scheduled_end = _parse_time(_get_cell(row, COL_SCHEDULED_END))

        # Detect informational rows (no scheduled_end required)
        is_end_of_show_row = bool(act_name and act_name.lower().strip() in ('end', 'end of show'))
        is_no_end_row = act_name and (
            'load in' in act_name.lower() or
            'on deck' in act_name.lower() or
            'stage time' in act_name.lower() or
            is_end_of_show_row
        )

        # END OF SHOW with no time: inherit the previous act's scheduled_end so
        # the row is placed immediately after the last set in the timeline.
        if is_end_of_show_row and not scheduled_start and last_scheduled_end:
            scheduled_start = last_scheduled_end

        # Skip rows without act name or required scheduled times
        # scheduled_end is optional — acts with no end time (e.g. final headliner) are allowed through
        if not act_name or not scheduled_start:
            continue

        if scheduled_end:
            last_scheduled_end = scheduled_end

        # Prefer in-memory cached total (avoids stale reads right after a write)
        screentime_total = _screentime_totals.get(
            act_name,
            _parse_screentime_seconds(_get_cell(row, COL_SCREENTIME_TOTAL))
        )

        act = Act(
            act_name=act_name,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            actual_start=_parse_time(_get_cell(row, COL_ACTUAL_START)),
            actual_end=_parse_time(_get_cell(row, COL_ACTUAL_END)),
            screentime_total_seconds=screentime_total,
            screentime_session_start=_screentime_sessions.get(act_name),
        )
        acts.append(act)

    return acts


def get_act(act_name: str) -> Optional[Act]:
    """Get a single act by name."""
    acts = get_schedule()
    for act in acts:
        if act.act_name == act_name:
            return act
    return None


def _find_row(act_name: str) -> Optional[int]:
    """Find the row number for an act using the cached row map."""
    return _row_cache.get(act_name)


def update_actual_start(act_name: str, actual_time: time) -> Optional[Act]:
    """Update the actual start time for an act."""
    sheet = _get_sheet()
    row_num = _find_row(act_name)

    if row_num is None:
        return None

    # actual_start column F = column 6
    sheet.update_cell(row_num, COL_ACTUAL_START, _format_time(actual_time))

    return get_act(act_name)


def update_actual_end(act_name: str, actual_time: time) -> Optional[Act]:
    """Update the actual end time for an act."""
    sheet = _get_sheet()
    row_num = _find_row(act_name)

    if row_num is None:
        return None

    # actual_end column G = column 7
    sheet.update_cell(row_num, COL_ACTUAL_END, _format_time(actual_time))

    return get_act(act_name)


def clear_actual_times(act_name: str) -> Optional[Act]:
    """Clear both actual start and end times for an act."""
    sheet = _get_sheet()
    row_num = _find_row(act_name)

    if row_num is None:
        return None

    # Clear actual_start (F), actual_end (G), and screentime (H)
    sheet.update_cell(row_num, COL_ACTUAL_START, "")
    sheet.update_cell(row_num, COL_ACTUAL_END, "")
    sheet.update_cell(row_num, COL_SCREENTIME_TOTAL, "")
    _screentime_sessions.pop(act_name, None)
    _screentime_totals.pop(act_name, None)

    return get_act(act_name)


def start_screentime(act_name: str) -> Optional[Act]:
    """Start a screentime session for an act."""
    _screentime_sessions[act_name] = datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()
    return get_act(act_name)


def stop_screentime(act_name: str) -> Optional[Act]:
    """Stop a screentime session and write accumulated total to sheet."""
    if act_name not in _screentime_sessions:
        print(f"[screentime] stop called but no active session for {act_name!r}")
        return get_act(act_name)

    session_start = _screentime_sessions.pop(act_name)
    now = datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()

    # Compute elapsed seconds, handle midnight crossing
    elapsed = time_to_secs(now) - time_to_secs(session_start)
    if elapsed < 0:
        elapsed += 86400

    print(f"[screentime] stop {act_name!r}: start={session_start} now={now} elapsed={elapsed}s")

    sheet = _get_sheet()
    # Single sheet read: find row number and current total simultaneously
    all_values = sheet.get_all_values()
    data_rows = all_values[HEADER_ROW:]
    row_num = None
    current_total = 0
    for i, row in enumerate(data_rows):
        if _get_cell(row, COL_ARTIST_NAME) == act_name:
            row_num = i + HEADER_ROW + 1
            current_total = _parse_screentime_seconds(_get_cell(row, COL_SCREENTIME_TOTAL))
            break

    if row_num is None:
        print(f"[screentime] row not found for {act_name!r} — sheet write skipped")
        return None

    new_total = current_total + elapsed
    _screentime_totals[act_name] = new_total
    print(f"[screentime] writing {new_total}s to row {row_num} col {COL_SCREENTIME_TOTAL}")
    try:
        sheet.update_cell(row_num, COL_SCREENTIME_TOTAL, _format_screentime(new_total))
        print(f"[screentime] write succeeded: {_format_screentime(new_total)}")
    except Exception as e:
        print(f"[screentime] Failed to write {act_name} total to sheet: {e}")

    return get_act(act_name)


def write_active_screentimes() -> None:
    """Write current running totals for all active sessions to the sheet.
    Called every poll interval so progress is preserved even if the container restarts."""
    if not _screentime_sessions:
        return

    tz = ZoneInfo(settings.TIMEZONE)
    now = datetime.now(tz=tz).time()
    now_secs = time_to_secs(now)
    sheet = _get_sheet()

    # Single sheet read; build a name→row_num map for all active sessions
    all_values = sheet.get_all_values()
    data_rows = all_values[HEADER_ROW:]
    active_names = set(_screentime_sessions)
    row_map: dict[str, int] = {}
    for i, row in enumerate(data_rows):
        name = _get_cell(row, COL_ARTIST_NAME)
        if name in active_names:
            row_map[name] = i + HEADER_ROW + 1

    for act_name, session_start in list(_screentime_sessions.items()):
        elapsed = now_secs - time_to_secs(session_start)
        if elapsed < 0:
            elapsed += 86400

        accumulated = _screentime_totals.get(act_name, 0)
        current_total = accumulated + max(0, elapsed)

        row_num = row_map.get(act_name)
        if row_num is None:
            print(f"[screentime] Could not find row for {act_name} during periodic write")
            continue
        try:
            sheet.update_cell(row_num, COL_SCREENTIME_TOTAL, _format_screentime(current_total))
        except Exception as e:
            print(f"[screentime] Periodic write failed for {act_name}: {e}")


def get_stage_name() -> str:
    """Get the stage name from config."""
    return settings.STAGE_NAME


def get_current_show() -> str:
    """Return the active tab name, or empty string in single-show mode."""
    return _show_tabs[_active_tab_index] if _show_tabs else ""


def has_next_show() -> bool:
    """Return True if there is a next show tab to advance to."""
    return len(_show_tabs) > 1 and _active_tab_index < len(_show_tabs) - 1


def get_next_show() -> str:
    """Return the next show tab name, or empty string if on the last show."""
    if has_next_show():
        return _show_tabs[_active_tab_index + 1]
    return ""


def advance_show() -> str:
    """Advance to the next show tab and reset all per-show state. Returns the new tab name."""
    global _active_tab_index, _sheet, _row_cache, _screentime_sessions, _screentime_totals
    if not has_next_show():
        raise ValueError("Already on the last show")
    _active_tab_index += 1
    _sheet = None  # Force _get_sheet() to reconnect to the new tab
    _row_cache = {}
    _screentime_sessions = {}
    _screentime_totals = {}
    new_tab = _show_tabs[_active_tab_index]
    print(f"[show] Advanced to tab: {new_tab!r}")
    return new_tab
