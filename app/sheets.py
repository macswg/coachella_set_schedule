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

from datetime import time
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from app.config import settings
from app.models import Act

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

_client: Optional[gspread.Client] = None
_sheet: Optional[gspread.Worksheet] = None


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
        _sheet = spreadsheet.sheet1

    return _sheet


def _parse_time(time_str: str) -> Optional[time]:
    """Parse a time string (HH:MM) to a time object."""
    if not time_str or time_str.strip() == "":
        return None
    try:
        parts = time_str.strip().split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


def _format_time(t: Optional[time]) -> str:
    """Format a time object to HH:MM string."""
    if t is None:
        return ""
    return t.strftime("%H:%M")


def get_schedule() -> list[Act]:
    """Fetch all acts from the Google Sheet."""
    sheet = _get_sheet()
    records = sheet.get_all_records()

    acts = []
    for row in records:
        act = Act(
            act_name=row.get("act_name", ""),
            scheduled_start=_parse_time(row.get("scheduled_start", "")),
            scheduled_end=_parse_time(row.get("scheduled_end", "")),
            actual_start=_parse_time(row.get("actual_start", "")),
            actual_end=_parse_time(row.get("actual_end", "")),
            notes=row.get("notes", "") or None,
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
    """Find the row number for an act (1-indexed, accounting for header)."""
    sheet = _get_sheet()
    records = sheet.get_all_records()

    for i, row in enumerate(records):
        if row.get("act_name") == act_name:
            return i + 2  # +1 for 1-indexing, +1 for header row

    return None


def update_actual_start(act_name: str, actual_time: time) -> Optional[Act]:
    """Update the actual start time for an act."""
    sheet = _get_sheet()
    row_num = _find_row(act_name)

    if row_num is None:
        return None

    # Find the actual_start column (D = column 4)
    sheet.update_cell(row_num, 4, _format_time(actual_time))

    return get_act(act_name)


def update_actual_end(act_name: str, actual_time: time) -> Optional[Act]:
    """Update the actual end time for an act."""
    sheet = _get_sheet()
    row_num = _find_row(act_name)

    if row_num is None:
        return None

    # Find the actual_end column (E = column 5)
    sheet.update_cell(row_num, 5, _format_time(actual_time))

    return get_act(act_name)


def clear_actual_times(act_name: str) -> Optional[Act]:
    """Clear both actual start and end times for an act."""
    sheet = _get_sheet()
    row_num = _find_row(act_name)

    if row_num is None:
        return None

    # Clear actual_start (D) and actual_end (E)
    sheet.update_cell(row_num, 4, "")
    sheet.update_cell(row_num, 5, "")

    return get_act(act_name)


def get_stage_name() -> str:
    """Get the stage name from config."""
    return settings.STAGE_NAME
