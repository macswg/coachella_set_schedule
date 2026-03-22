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

import gspread
from google.oauth2.service_account import Credentials

from app.config import settings
from app.models import Act

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# Column indices (1-based for gspread)
COL_ARTIST_NAME = 2      # B - "artist name"
COL_SCHEDULED_START = 4  # D - "scheduled start"
COL_SCHEDULED_END = 5    # E - "scheduled end"
COL_ACTUAL_START = 6     # F - "actual time on"
COL_ACTUAL_END = 7       # G - "actual time off"
COL_SCREENTIME_TOTAL = 8  # H - "screentime total seconds"

HEADER_ROW = 5  # Header is on row 5, data starts row 6

_client: Optional[gspread.Client] = None
_sheet: Optional[gspread.Worksheet] = None

# In-memory screentime session tracking (survives schedule list rebuilds)
_screentime_sessions: dict[str, time] = {}


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
        if settings.GOOGLE_SHEET_TAB:
            _sheet = spreadsheet.worksheet(settings.GOOGLE_SHEET_TAB)
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
    sheet = _get_sheet()
    # Get all values starting from the data row (after header)
    all_values = sheet.get_all_values()
    data_rows = all_values[HEADER_ROW:]  # Skip header rows (0-indexed, so row 6 = index 5)

    acts = []
    for row in data_rows:
        act_name = _get_cell(row, COL_ARTIST_NAME)
        scheduled_start = _parse_time(_get_cell(row, COL_SCHEDULED_START))
        scheduled_end = _parse_time(_get_cell(row, COL_SCHEDULED_END))

        # Detect informational rows (no scheduled_end required)
        is_no_end_row = act_name and ('load in' in act_name.lower() or 'on deck' in act_name.lower())

        # Skip rows without act name or required scheduled times
        if not act_name or not scheduled_start or (not scheduled_end and not is_no_end_row):
            continue

        screentime_total = _parse_screentime_seconds(_get_cell(row, COL_SCREENTIME_TOTAL))

        act = Act(
            act_name=act_name,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            actual_start=_parse_time(_get_cell(row, COL_ACTUAL_START)),
            actual_end=_parse_time(_get_cell(row, COL_ACTUAL_END)),
            notes=None,
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
    """Find the row number for an act (1-indexed, accounting for header on row 5)."""
    sheet = _get_sheet()
    all_values = sheet.get_all_values()
    data_rows = all_values[HEADER_ROW:]  # Skip header rows

    for i, row in enumerate(data_rows):
        if _get_cell(row, COL_ARTIST_NAME) == act_name:
            return i + HEADER_ROW + 1  # Convert back to 1-indexed sheet row

    return None


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

    return get_act(act_name)


def start_screentime(act_name: str) -> Optional[Act]:
    """Start a screentime session for an act."""
    _screentime_sessions[act_name] = datetime.now().time()
    return get_act(act_name)


def stop_screentime(act_name: str) -> Optional[Act]:
    """Stop a screentime session and write accumulated total to sheet."""
    if act_name not in _screentime_sessions:
        return get_act(act_name)

    session_start = _screentime_sessions.pop(act_name)
    now = datetime.now().time()

    # Compute elapsed seconds, handle midnight crossing
    start_secs = session_start.hour * 3600 + session_start.minute * 60 + session_start.second
    now_secs = now.hour * 3600 + now.minute * 60 + now.second
    elapsed = now_secs - start_secs
    if elapsed < 0:
        elapsed += 86400

    sheet = _get_sheet()
    row_num = _find_row(act_name)

    if row_num is None:
        return None

    # Read current total from sheet (treat sheet as authoritative)
    all_values = sheet.get_all_values()
    data_rows = all_values[HEADER_ROW:]
    current_total = 0
    for row in data_rows:
        if _get_cell(row, COL_ARTIST_NAME) == act_name:
            current_total = _parse_screentime_seconds(_get_cell(row, COL_SCREENTIME_TOTAL))
            break

    new_total = current_total + elapsed
    sheet.update_cell(row_num, COL_SCREENTIME_TOTAL, new_total)

    return get_act(act_name)


def get_stage_name() -> str:
    """Get the stage name from config."""
    return settings.STAGE_NAME
