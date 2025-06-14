from utils import load_users, load_logs, format_time, now_trimmed, format_duration
from datetime import datetime

def find_active_workers():
    users = load_users()
    logs = load_logs()

    # Map user ID to name for quick lookup
    user_map = {u['id']: u['name'] for u in users}

    print("\n=== Active Workers (Clocked In) ===")
    found = False

    for log in logs:
        if log["clock_out"] is None:
            uid = log["user_id"]
            name = user_map.get(uid, uid)
            start = log["clock_in"]
            end = now_trimmed()
            duration_str = format_duration(start, end, ongoing=True)
            start_str = format_time(start)
            print(f"{name} - Clocked in at {start_str} | {duration_str}")
            found = True

    if not found:
        print("No one is currently clocked in.")

if __name__ == "__main__":
    find_active_workers()
