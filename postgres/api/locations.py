import copy
from postgres.api.helpers import add_sql, delete_sql

# DATABASE
def add_location(cur, value):
    cur.execute(add_sql("locations", ["address"]), [value])

# never happens... it just deletes and re-adds since address is
# the only identifier
def edit_location(cur, value):
    pass

def delete_location(cur, value):
    cur.execute(delete_sql("locations", "address"), [value])

# LOCAL
def add_local_location(new, data, cur):
    cur.execute("SELECT name FROM companies", [])
    companies_db = {row[0] for row in cur.fetchall()}
    companies_local = sorted({
        company
        for location_dict in data.values()
        for company in location_dict.keys()})
    companies = sorted(companies_db.union(companies_local))
    data[new["address"]] = {name: [] for name in companies}

def delete_local_location(old, data):
    del data[old["address"]]
def delete_local_location_by_id(address, data):
    del data[address]

def edit_local_location(new, data, _cur, old=None):
    if old == None:
        old = copy.deepcopy(new)
    if old["address"] in data:
        data[new["address"]] = data.pop(old["address"])
