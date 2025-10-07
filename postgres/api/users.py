from postgres.api.helpers import add_sql, update_sql, delete_sql

USER_DB_FIELDS = ("id", "name", "pin")
CONTRACT_DB_FIELDS = ("company", "user_id", "custom_settings")

def _user_fields_and_values(value):
    tmp = [(f,v) for f,v in value.items() if f in USER_DB_FIELDS]
    return tuple(map(list, zip(*tmp)))

def _contract_fields_and_values(value):
    tmp = [(f,v) for f,v in value.items() if _map_contract(f) in CONTRACT_DB_FIELDS]
    settings = {k:v for k,v in value.items() if 
        _map_contract(k) not in USER_DB_FIELDS and
        _map_contract(k) not in CONTRACT_DB_FIELDS}
    tmp.append(("custom_settings", settings))
    return tuple(map(list, zip(*tmp)))

def _map_contract(field):
    if field == "id": return "user_id"
    return field

def add_user(cur, value):
    fields, values = _user_fields_and_values(value)
    cur.execute(add_sql("users", fields), values)

    fields, values = _contract_fields_and_values(value)
    cur.execute(add_sql("contracts", fields), values)

def update_user(cur, value):
    fields, values = _user_fields_and_values(value)
    id_idx = fields.index("id")
    id = values[id_idx]

    values = [v for f, v in zip(fields, values) if f != "id"]

    sql = update_sql("users", fields, "id")
    cur.execute(sql, values + [id])

def delete_user(cur, value):
    fields, values = _user_fields_and_values(value)
    id_idx = fields.index("id")
    id = values[id_idx]

    sql = delete_sql("users", "id")
    cur.execute(sql, [id])
