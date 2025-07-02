import json
import os
import sys
from datetime import datetime

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    return os.path.join(base_path, relative_path)


# === CONFIGURATIONS === #
COMPANY_FOLDER = resource_path("Database/Fyrirtaeki")  # Base directory for company folders
USER_FILE = resource_path("Database/users.json")  # Path to user definitions
EXPORT_FOLDER = resource_path("Database/reports")  # Folder for exported reports
TASK_FILE = resource_path("Database/task_config.json")  # Path to task configuration



# === USER MANAGEMENT === #

# Load user definitions from users.json
def load_users(filename=None):
    if filename is None:
        filename = USER_FILE
    print(f"Loading users from: {filename}")  # debug
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
    return logs and logs[-1].get("clock_out") is None




# === TASK MANAGEMENT === #

def load_task_config(filename=TASK_FILE):
    with open(filename, "r") as f:
        return json.load(f)

def get_locations_for_user(user, task_config):
    # Find all locations that include this user's company
    return [
        location for location, roles in task_config.items()
        if user["company"] in roles
    ]

def get_tasks_for_user(user, location, task_config):
    return task_config.get(location, {}).get(user["company"], [])




# === FILE PATHS === #

# Get the path to an employee's personal log file
def get_employee_log_path(user):
    folder = os.path.join(COMPANY_FOLDER, user["company"])
    os.makedirs(folder, exist_ok=True)  # create folders if missing
    return os.path.join(folder, f"{user['id']}.json")



# === LOG HANDLING === #

# Load logs for a specific employee
def load_employee_logs(user):
    path = get_employee_log_path(user)
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)
    
# Save logs for a specific employee
def save_employee_logs(user, logs):
    path = get_employee_log_path(user)
    with open(path, "w") as f:
        json.dump(logs, f, indent=4)

def create_shift_entry(task, location):
    return {
        "task": task,
        "location": location,
        "clock_in": now_trimmed(),
        "clock_out": None
    }

def close_last_shift(logs):
    for log in reversed(logs):
        if log["clock_out"] is None:
            log["clock_out"] = now_trimmed()
            return log
    return None



# === TIME FORMATTING & CALCULATION ===

# Get current time without seconds or microseconds
def now_trimmed():
    return datetime.now().replace(second=0, microsecond=0).isoformat()

# Format time for display
def format_time(iso):
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%b %d, %H:%M")  # e.g. "Jun 07, 14:31"

# Format duration between two times (and word it)
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

# Basic duration calculator
def calc_duration(start, end):
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    return str(end_dt - start_dt)
