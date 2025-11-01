from datetime import datetime

def add_sql(table, fields):
    placeholders = ", ".join(["%s"] * len(fields))
    columns = ", ".join(fields)
    return f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
def update_sql(table, fields, where):
    set_clause = ", ".join(f"{f} = %s" for f in fields if f != where)
    dt = datetime.now()
    set_clause = set_clause + f", updated_at = '{dt.isoformat()}'"
    return f"UPDATE {table} SET {set_clause} WHERE {where} = %s"

def delete_sql(table, where):
    return f"DELETE FROM {table} WHERE {where} = %s"
