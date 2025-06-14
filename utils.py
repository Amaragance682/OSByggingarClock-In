import json
from datetime import datetime


# gets the users and log files
def load_users(filename="users.json"):
    with open(filename, "r") as f:
        return json.load(f)

def load_logs(filename="logs.json"):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


# write method, breytir gögnum í json fileinu
def save_logs(logs, filename="logs.json"):
    with open(filename, "w") as f:
        json.dump(logs, f, indent=4)


# gefur núverandi tíma trimmed
def now_trimmed(): # trimming method for time
    return datetime.now().replace(second=0, microsecond=0).isoformat()


# rétta format fyrir tíma
def format_time(iso):
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%b %d, %H:%M")  # e.g. "Jun 07, 14:31"

def format_duration(start_iso, end_iso, ongoing=False):
    start_dt = datetime.fromisoformat(start_iso)
    end_dt = datetime.fromisoformat(end_iso)
    duration = end_dt - start_dt

    total_minutes = int(duration.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    start_str = start_dt.strftime("%H:%M")
    end_str = end_dt.strftime("%H:%M")

    verb = "Working" if ongoing else "Worked"
    return f"{verb} {hours} hours and {minutes} minutes (from {start_str} to {end_str})"


# reikningar fyrir start duration og end duration
def calc_duration(start, end):
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    return str(end_dt - start_dt)