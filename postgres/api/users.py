import psycopg2
from postgres.api.helpers import add_sql, update_sql, delete_sql
from postgres.api.requests import delete_request

USER_DB_FIELDS = ("id", "name", "pin")
CONTRACT_DB_FIELDS = ("company", "user_id", "custom_settings")
CONTRACT_DIRECT = ("company")
REQUIRED = ("id", "name", "pin", "company")

def _user_fields_and_values(value):
    tmp = [(f,v) for f,v in value.items() if f in USER_DB_FIELDS]
    return tuple(map(list, zip(*tmp)))

def _contract_fields_and_values(value):
    tmp = [(f,v) for f,v in value.items()]
    return tuple(map(list, zip(*tmp)))

def _map_contract(cur, value):
    fin = {}
    custom_settings = {}

    for f,v in value.items():
        if f in CONTRACT_DIRECT:
            fin[f] = v
        if f not in REQUIRED:
            custom_settings[f] = v

    fin["custom_settings"] = psycopg2.extras.Json(custom_settings)
    fin["user_id"] = value["id"]

    return fin

def add_user(cur, value):
    fields, values = _user_fields_and_values(value)
    cur.execute(add_sql("users", fields), values)

    fields, values = _contract_fields_and_values(_map_contract(cur, value))
    cur.execute(add_sql("contracts", fields), values)

def update_user(cur, value):
    user_fields, user_values = _user_fields_and_values(value)
    user_id = value["id"]

    user_values = [v for f, v in zip(user_fields, user_values) if f != "id"]

    sql = update_sql("users", user_fields, "id")
    cur.execute(sql, user_values + [user_id])

    contract_fields, contract_values = _contract_fields_and_values(_map_contract(cur, value))

    sql = update_sql("contracts", contract_fields, "user_id")
    cur.execute(sql, contract_values + [user_id])

def delete_user(cur, value):
    fields, values = _user_fields_and_values(value)
    id_idx = fields.index("id")
    id = values[id_idx]

    sql = delete_sql("users", "id")
    cur.execute(sql, [id])

    sql = delete_sql("contracts", "user_id")
    cur.execute(sql, [id])
