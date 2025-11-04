import json
from datetime import datetime
from pathlib import Path

def read(path):
    try:
        with open(Path(path), "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []
    return data

def resolve_from_row(row, cur):
    if "user_id" in row.keys():
        user_id = row["user_id"]
        company = row["company"]
    else:
        cur.execute("SELECT user_id, company FROM contracts WHERE id = %s",
                    [row["contract_id"]])
        user_id, company = cur.fetchone()[:2]
    return (user_id, company)

CACHE_FILE = Path("cache.json")

def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

def update_last_sync():
    cache = load_cache()
    now = datetime.now().isoformat()
    cache["last_sync"] = now
    save_cache(cache)
    print(f"Last sync updated: {now}")

