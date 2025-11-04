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

def add_local_task(new, data, _cur):
    new_task = {
        "id": new["id"],
        "name": new["name"],
        "completed": new["completed"]
    }
    company = new["company"]
    location = new["location"]

    data[location][company].append(new_task)

def delete_local_task(old, data):
    company = old["company"]
    location = old["location"]
    data[location][company][:] = [d for d in data[location][company] if d["id"] != old["id"]]
def delete_local_task_from_id(id, data):
    for _, companies in data.items():
        for _, tasks in companies.items():
            for i, task in enumerate(tasks):
                if task.get("id") == id:
                    del tasks[i]
def edit_local_task(new, data, _cur):
    new_company = new["company"]
    new_location = new["location"]

    new_task = {
        "id": new["id"],
        "name": new["name"],
        "completed": new["completed"]
    }

    for companies_dict in data.values():
        for tasks in companies_dict.values():
            tasks[:] = [d for d in tasks if d["id"] != new_task["id"]]
    data[new_location][new_company].append(new_task)
