from postgres.api.helpers import add_sql, delete_sql

def add_location(cur, value):
    cur.execute(add_sql("locations", ["address"]), [value])

# never happens... it just deletes and re-adds since address is
# the only identifier
def edit_location(cur, value):
    pass

def delete_location(cur, value):
    cur.execute(delete_sql("locations", "address"), [value])
