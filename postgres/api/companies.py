import copy
from postgres.api.helpers import add_sql, delete_sql

def add_company(cur, value):
    cur.execute(add_sql("companies", ["name"]), [value])
    print("should have added:", value)

# never happens... it just deletes and re-adds since name is
# the only identifier
def edit_company(cur, value):
    pass

def delete_company(cur, value):
    cur.execute(delete_sql("companies", "name"), [value])

def add_local_company(new, data, _cur):
    for _, loc in data.items():
        if new["name"] not in loc:
            loc[new["name"]] = []

def edit_local_company(new, data, _cur, old=None):
    if old == None:
        old = copy.deepcopy(new)
    for _, loc in data.items():
        if old["name"] in loc:
            loc[new["name"]] = loc.pop(old["name"])

def delete_local_company(old, data):
    for _, loc in data.items():
        del loc[old["name"]]
def delete_local_company_by_id(name, data):
    for _, loc in data.items():
        del loc[name]
