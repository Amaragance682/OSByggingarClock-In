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
    cur.execute(sql, contract_values)

def delete_user(cur, value):
    fields, values = _user_fields_and_values(value)
    id_idx = fields.index("id")
    id = values[id_idx]

    sql = delete_sql("users", "id")
    cur.execute(sql, [id])

    sql = delete_sql("contracts", "user_id")
    cur.execute(sql, [id])

def add_local_user(new, data, _cur):
    new_user = {
        "id": new["id"],
        "name": new["name"],
        "pin": new["pin"]
    }
    data.append(new_user)
def delete_local_user(old, data):
    data[:] = [d for d in data if d["id"] != old["id"]]
def delete_local_user_from_id(id, data):
    data[:] = [d for d in data if d["id"] != id]
def edit_local_user(new, data, _cur):
    for i, d in enumerate(data):
        if d["id"] == new["id"]:
            data[i] = new
            break
def add_local_contract(new, data, _cur):
    company = new["company"]

    for i, d in enumerate(data):
        if d["id"] == new["user_id"]:
            data[i]["company"] = company
            for i2, d2 in new["custom_settings"].items():
                data[i][i2] = d2
def edit_local_contract(new, data, _cur):
    for i, d in enumerate(data):
        if d["id"] == new["user_id"]:
            for i2, d2 in new["custom_settings"].items():
                data[i][i2] = d2
            data[i]["company"] = new["company"]
