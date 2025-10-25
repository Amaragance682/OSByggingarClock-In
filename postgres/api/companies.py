from postgres.api.helpers import add_sql, delete_sql

def add_company(cur, value):
    cur.execute(add_sql("companies", ["name"]), [value])

# never happens... it just deletes and re-adds since name is
# the only identifier
def edit_company(cur, value):
    pass

def delete_company(cur, value):
    cur.execute(delete_sql("companies", "name"), [value])
