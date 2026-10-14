"""Alarm data model shared by the GUI (main.py) and the background worker (worker.py)."""

import uuid
from datetime import datetime

# Full English day names, matching what strftime("%A") returns.
DEFAULT_DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def normalize_days(days):
    """
    Converts day names to the full names in DEFAULT_DAYS, in week order.

    Accepts any capitalisation and abbreviations of 3+ letters ("mon", "Tues.",
    "WEDNESDAY"). Unrecognised names are dropped. This repairs alarms saved by
    the old text field, which stored whatever was typed (e.g. "Mon").
    """
    cleaned = {str(day).strip().rstrip(".").lower() for day in days}
    return [
        full_name
        for full_name in DEFAULT_DAYS
        if any(
            len(name) >= 3 and full_name.lower().startswith(name) for name in cleaned
        )
    ]


class Alarm:
    """A single repeating alarm, stored on disk by alarm_storage."""

    def __init__(self, time_str, title, days=None, is_active=True):
        """
        Blueprint for a single alarm object.

        :param time_str: 24-hour time string in "HH:MM" format (e.g., "08:00")
        :param title: String title/message for the notification
        :param days: List of full day names (e.g., ["Monday", "Wednesday"]).
            If None, the alarm runs EVERY DAY.
        :param is_active: Boolean indicating if the alarm is currently turned on
        """
        self.id = str(uuid.uuid4())  # Unique ID for internal tracking
        self.time_str = time_str
        self.title = title
        self.is_active = is_active
        self.last_triggered_date = (
            None  # Prevents the alarm from spamming during that match minute
        )

        self.days = DEFAULT_DAYS if days is None else days

    def should_trigger(self, now=None):
        """
        Checks if the alarm matches the current system time and day.

        Returns True only when the alarm is active, the time and weekday match
        exactly, and it hasn't already fired today.

        :param now: datetime to check against (defaults to the current time)
        """

        now = datetime.now() if now is None else now
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")
        current_day = now.strftime("%A")  # Gets full day name (e.g., "Monday")

        if (
            self.is_active
            and self.time_str == current_time
            and current_day in normalize_days(self.days)
            and self.last_triggered_date != current_date
        ):
            return True

        return False
