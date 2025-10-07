SHIFT_DB_FIELDS = ("id", "contract_id", "location", "task_id", "clock_in", "clock_out", "extra")
REQUIRED = ("id", "task", "location", "clock_in", "clock_out")

def _shift_fields_and_values(value):
    tmp = [(f,v) for f,v in value.items() if f in SHIFT_DB_FIELDS]
    return tuple(map(list, zip(*tmp)))

def _map_shift(cur, value):
    extra = {}
    fin = {}
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
    for f,v in value.items():
        if f not in REQUIRED:
            extra[f] = v
        else:


def add_shift(cur, value):
    fields, values = _shift_fields_and_values(value)
