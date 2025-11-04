from datetime import datetime
from postgres.api.helpers import add_sql, delete_sql, update_sql
import psycopg2

SHIFT_DB_FIELDS = ("id", "contract_id", "location", "task_id", "clock_in", "clock_out", "extra")
REQUIRED = ("id", "task", "location", "clock_in", "clock_out", "user_id", "company")
DIRECT = ("id", "location", "clock_in", "clock_out")

def _shift_fields_and_values(value):
    print(value)
    tmp = [(f,v) for f,v in value.items()]
    return tuple(map(list, zip(*tmp)))

def _map_shift(cur, value):
    extra = {}
    fin = {}
    
    for f,v in value.items():
        if f in DIRECT:
            fin[f] = v
        if f not in REQUIRED:
            extra[f] = v

    fin["extra"] = psycopg2.extras.Json(extra)

    cur.execute("SELECT id FROM contracts WHERE user_id = %s AND company = %s",
                [value["user_id"],
                value["company"]])
    contract_id = cur.fetchone()[0]
    fin["contract_id"] = contract_id

    cur.execute("SELECT id FROM tasks WHERE company = %s AND location = %s AND name = %s",
                [value["company"],
                value["location"],
                value["task"]])
    task_id = cur.fetchone()[0]
    fin["task_id"] = task_id

    return fin

def add_shift(cur, value):
    fields, values = _shift_fields_and_values(_map_shift(cur, value))
    cur.execute(add_sql("shifts", fields), values)

def edit_shift(cur, value):
    fields, values = _shift_fields_and_values(_map_shift(cur, value))
    id_idx = fields.index("id")
    id = values[id_idx]

    values = [v for f, v in zip(fields, values) if f != "id"]

    sql = update_sql("shifts", fields, "id")
    cur.execute(sql, values + [id])

def delete_shift(cur, value):
    fields, values = _shift_fields_and_values(_map_shift(cur, value))
    id_idx = fields.index("id")
    id = values[id_idx]

    sql = delete_sql("shifts", "id")
    cur.execute(sql, [id])

def add_local_shift(new, data, cur):
    contract_id = new["contract_id"]
    cur.execute("SELECT company, user_id FROM contracts WHERE id=%s", [contract_id])
    company, user_id = cur.fetchone()

    task_id = new["task_id"]
    location = new["location"]

    cur.execute("SELECT name FROM tasks WHERE id=%s", [task_id])
    task = cur.fetchone()[0]

    new_shift = {
        "id": new["id"],
        "task": task,
        "location": location,
        "clock_in": new["clock_in"].isoformat()
    }

    if "clock_out" in new.keys():
        new_shift["clock_out"] = new["clock_out"].isoformat()

        for field, value in new["extra"] or {}.items():
            new_shift[field] = value

    data.append(new_shift)
    return (user_id, company)

def delete_local_shift(old, data, cur):
    contract_id = old["contract_id"]
    cur.execute("SELECT user_id, company FROM contracts WHERE id=%s", [contract_id])
    user_id, company = cur.fetchone()
    data[:] = [d for d in data if d["id"] != old["id"]]
    return (user_id, company)

def delete_local_shift_by_id(id, data):
    data[:] = [d for d in data if d["id"] != id]

def edit_local_shift(new, data, cur):
    print("editing shift:", new)
    contract_id = new["contract_id"]

    task_id = new["task_id"]
    location = new["location"]

    cur.execute("SELECT user_id, company FROM contracts WHERE id=%s", [contract_id])
    user_id, company = cur.fetchone()

    cur.execute("SELECT name FROM tasks WHERE id=%s", [task_id])
    task = cur.fetchone()[0]

    new_shift = {
        "id": new["id"],
        "task": task,
        "location": location,
        "clock_in": new["clock_in"].isoformat()
    }
    if "clock_out" in new.keys():
        new_shift["clock_out"] = new["clock_out"].isoformat()
        for field, value in new["extra"] or {}.items():
            new_shift[field] = value

    for d in data:
        if d["id"] == new["id"]:
            d.update(new_shift)
    return (user_id, company)


if __name__ == "__main__":
    pass
