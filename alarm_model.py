import uuid
from datetime import datetime

class Alarm:
    def __init__(self, time_str, title, days=None, is_active=True):
        """
        Blueprint for a single alarm object.
        
        :param time_str: String format "HH:MM" (e.g., "08:00")
        :param title: String title/message for the notification
        :param days: List of strings for specific days (e.g., ["Monday", "Wednesday"])
            If left empty/None, it defaults to running EVERYDAY.
        :param is_active: Boolean indicating if the alarm is currently turned on
        """
        self.id = str(uuid.uuid4())  # Unique ID for internal tracking
        self.time_str = time_str
        self.title = title
        self.is_active = is_active
        self.last_triggered_date = None  # Prevents the alarm from spamming during that match minute
        
        # Constructor logic for days: 
        # If no days are provided, assign it all 7 days (Runs Everyday)
        if days is None:
            self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        else:
            self.days = days

    def should_trigger(self):
        """
        Checks if the alarm matches the current system time and day.
        """

        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")
        current_day = now.strftime("%A")  # Gets full day name (e.g., "Monday")

        # Condition check:
        if (self.is_active and self.time_str == current_time and current_day in self.days and self.last_triggered_date != current_date):
            return True
            
        return False