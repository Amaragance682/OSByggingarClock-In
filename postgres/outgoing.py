import time
import os
import psycopg2
from dotenv import load_dotenv
from watchdog.observers import Observer
from psycopg2.pool import SimpleConnectionPool
from lib.watcher import JSONChangeHandler

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')

pool = SimpleConnectionPool(1, 4, dsn=os.getenv("DATABASE_URL"), sslmode="require")

def with_db(func):
    def wrapper(*args, **kwargs):
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                result = func(cur, *args, **kwargs)
                conn.commit()
                return result
        except Exception as e:
            conn.rollback()
            print(f"DB error: {e}")
        finally:
            pool.putconn(conn)
    return wrapper

def init_observer(callback, path):
    watcher = JSONChangeHandler(callback, path)
    observer = Observer()
    observer.schedule(watcher, path=path, recursive=True)
    observer.start()
    return observer

@with_db
def users_callback(cur, changes):
    for change in changes:
        operation = change["type"]
        value = change["value"]
        if operation == "added":
            print(value)
        if operation == "removed":
            print(value)
        if operation == "changed":
            print(value)
@with_db
def tasks_callback(cur, changes):
    print(changes)
@with_db
def shifts_callback(cur, changes):
    print(changes)
@with_db
def requests_callback(cur, changes):
    print(changes)

observers = []

observers.append(init_observer(users_callback, "Database/users.json"))
observers.append(init_observer(tasks_callback, "Database/task_config.json"))
observers.append(init_observer(shifts_callback, "Database/Fyrirtaeki"))
observers.append(init_observer(requests_callback, "Database/Requests"))

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    for o in observers:
        o.stop()
for o in observers:
    o.join()

#conn.commit()
#cur.close()
#conn.close()
