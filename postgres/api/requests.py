from postgres.api.helpers import add_sql, update_sql, delete_sql
import psycopg2

REQUEST_DB_FIELD = ("id", "user_id", "task_id", "company", "location", "requested_start", "requested_end", "reason", "status", "extra")
REQUIRED = ("id", "task", "location", "company", "requested_end", "requested_start", "reason", "status", "user_id")
DIRECT = ("id", "user_id", "location", "company", "requested_start", "requested_end", "reason", "status")

def _request_fields_and_values(value):
    tmp = [(f,v) for f,v in value.items()]
    return tuple(map(list, zip(*tmp)))

def _map_request(cur, value):
    fin = {}
    extra = {}

    for f,v in value.items():
        if f in DIRECT:
            fin[f] = v
        if f not in REQUIRED:
            extra[f] = v

    fin["extra"] = psycopg2.extras.Json(extra)

    cur.execute("SELECT id FROM tasks WHERE name = %s AND location = %s", [value["task"], value["location"]])
    task_id = cur.fetchone()[0]
    fin["task_id"] = task_id

    print(fin)

    return fin

def add_request(cur, value):
    print(value)
    fields, values = _request_fields_and_values(_map_request(cur, value))
    cur.execute(add_sql("requests", fields), values)

def edit_request(cur, value):
    fields, values = _request_fields_and_values(_map_request(cur, value))
    id_idx = fields.index("id")
    id = values[id_idx]

    values = [v for f, v in zip(fields, values) if f != "id"]

    sql = update_sql("requests", fields, "id")
    cur.execute(sql, values + [id])

def delete_request(cur, value):
    fields, values = _request_fields_and_values(_map_request(cur, value))
    id_idx = fields.index("id")
    id = values[id_idx]

    sql = delete_sql("requests", "id")
    cur.execute(sql, [id])
