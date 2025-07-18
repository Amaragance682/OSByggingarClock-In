import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

def resource_path(relative_path):
    base_path = getattr(
        sys, '_MEIPASS',
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    )
    return os.path.join(base_path, relative_path)


# === CONFIGURATIONS === #
COMPANY_FOLDER = resource_path("Database/Fyrirtaeki")
USER_FILE      = resource_path("Database/users.json")
EXPORT_FOLDER  = resource_path("Database/reports")
TASK_FILE      = resource_path("Database/task_config.json")


# === USER MANAGEMENT === #


def save_users(users: List[Dict[str,Any]]) -> None:
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def load_task_config() -> Dict[str,Any]:
    with open(TASK_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_task_config(cfg: Dict[str,Any]) -> None:
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# legacy override/alternate loader (debug)
def load_users(filename=None):
    if filename is None:
        filename = resource_path(os.path.join('Database','users.json'))
    print(f"Loading users from: {filename}")
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_user_by_pin(pin, users=None):
    if users is None:
        users = load_users()
    for user in users:
        if str(user.get("pin")) == str(pin):
            return user
    return None

def is_clocked_in(user):
    logs = load_employee_logs(user)
    return bool(logs and logs[-1].get("clock_out") is None)


# === TASK MANAGEMENT === #


def get_locations_for_user(user: Dict[str,Any],
                           task_config: Dict[str,Any]
                           ) -> List[str]:
    return [
        location
        for location, companies in task_config.items()
        if user["company"] in companies
    ]

def get_tasks_for_user(user: Dict[str,Any],
                       location: str,
                       task_config: Dict[str,Any]
                       ) -> List[str]:
    """
    Return all task-names for this user's company at this location,
    whether completed or not (handles legacy string lists too).
    """
    raw = task_config.get(location, {}).get(user["company"], [])
    names: List[str] = []
    for item in raw:
        if isinstance(item, dict):
            names.append(item["name"])
        else:
            names.append(item)
    return names

def get_incomplete_tasks(task_config: Dict[str,Any],
                         company: str,
                         location: str
                         ) -> List[str]:
    """
    Return only those task-names whose `completed` flag is False.
    Falls back to treating all legacy strings as incomplete.
    """
    raw = task_config.get(location, {}).get(company, [])
    names: List[str] = []
    for item in raw:
        if isinstance(item, dict):
            if not item.get("completed", False):
                names.append(item["name"])
        else:
            names.append(item)
    return names


# === FILE PATHS & LOG HANDLING === #

def get_employee_log_path(user):
    folder = os.path.join(COMPANY_FOLDER, user["company"])
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{user['id']}.json")

def load_employee_logs(user):
    path = get_employee_log_path(user)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_employee_logs(user, logs):
    path = get_employee_log_path(user)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4)

def create_shift_entry(user, task, location):
    """
    Called when employee clocks in.
    Records the real clock_in time, plus commute (one-way) in minutes.
    """
    now = datetime.now().replace(second=0, microsecond=0)
    commute = int(user.get("commute_minutes", 0))
    return {
        "task":       task,
        "location":   location,
        "clock_in":   now.isoformat(),
        "commute":    commute,           # one‑way commute
        # we'll add lunch and clock_out later
    }

def close_last_shift(logs, user):
    """
    Called when employee clocks out.
    Finds the last open shift and stamps the real clock_out time,
    preserving commute from the original entry.
    """
    for entry in reversed(logs):
        if entry.get("clock_out") is None:
            now = datetime.now().replace(second=0, microsecond=0)
            entry["clock_out"] = now.isoformat()
            # lunch_taken & lunch_minutes should already have been set by the UI
            return entry
    return None


# === TIME FORMATTING & CALCULATION === #

def now_trimmed():
    return datetime.now().replace(second=0, microsecond=0).isoformat()

def format_time(iso):
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%b %d, %H:%M")

def format_duration(start_iso, end_iso, ongoing=False):
    """
    Reports Worked Xh Ym (ignores commute entirely).
    ongoing=True will label “Working”, else “Worked”.
    """
    start = datetime.fromisoformat(start_iso)
    end   = datetime.fromisoformat(end_iso)
    total_mins = int((end - start).total_seconds() // 60)
    h, m      = divmod(total_mins, 60)
    verb      = "Working" if ongoing else "Worked"
    return f"{verb} {h}h {m}m (from {start:%H:%M} to {end:%H:%M})"


def calc_duration(start, end):
    return str(datetime.fromisoformat(end) - datetime.fromisoformat(start))
