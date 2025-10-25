from postgres.api.helpers import add_sql, delete_sql, update_sql

DIRECT = ("id", "name", "completed", "location", "company")

def _task_fields_and_values(value):
    tmp = [(f,v) for f,v in value.items() if f in DIRECT]
    return tuple(map(list, zip(*tmp)))

def add_task(cur, value):
    fields, values = _task_fields_and_values(value)
    cur.execute(add_sql("tasks", fields), values)

def edit_task(cur, value):
    fields, values = _task_fields_and_values(value)
    task_id = value["id"]
    task_values = [v for f, v in zip(fields, values) if f != "id"]

    sql = update_sql("tasks", fields, "id")
    cur.execute(sql, task_values + [task_id])

def delete_task(cur, value):
    cur.execute(delete_sql("tasks", "id"), [value["id"]])
