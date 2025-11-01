import threading
import postgres.api.requests as requests
import postgres.api.shifts as shifts
import postgres.api.users as users
import postgres.api.locations as locations
import postgres.api.companies as companies
import postgres.api.tasks as tasks
from rich.console import Console
from rich.table import Table
from rich import box
import time
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from watchdog.observers import Observer
from psycopg2.pool import SimpleConnectionPool
from lib.watcher import JSONChangeHandler
import re
from apps.app import LOCATION

class Outgoing():
    def __init__(self):
        load_dotenv()
        self.console = Console()

        self.pool = SimpleConnectionPool(1, 1, dsn=os.getenv("DATABASE_URL"), sslmode="require")

        self.observers = []
        self.start_observers()

    def lock_file(self, path):
        for t in self.observers:
            _, watcher, o_path = t
            if o_path in path:
                watcher.lock(path)
    def unlock_file(self, path, data):
        for t in self.observers:
            _, watcher, o_path = t
            if o_path in path:
                watcher.unlock(path, data)

    def start_observers(self):
        t = threading.Thread(target=self._run_observers, daemon=True)
        t.start()

    def _run_observers(self):
        self.observers.append(self.init_observer(self.callback, "Database/"))

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            for o, _, _ in self.observers:
                o.stop()
            for o, _, _ in self.observers:
                o.join()

    def with_db(self, func):
        def wrapper(*args, **kwargs):
            conn = self.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SET app.source = '{LOCATION}'")
                    func(cur, *args, **kwargs)
                    conn.commit()
                    return True
            except psycopg2.Error as e:
                conn.rollback()
                print(f"DB error: {e}")
                return False
            finally:
                self.pool.putconn(conn)
        return wrapper

    def init_observer(self, callback, path):
        if os.path.isfile(path):
            watch_dir = os.path.dirname(os.path.abspath(path))
        else:
            watch_dir = path
        watcher = JSONChangeHandler(callback, path)
        observer = Observer()
        observer.schedule(watcher, path=watch_dir, recursive=True)
        observer.start()
        return (observer, watcher, path)
    
    def callback(self, changes):
        def handle_change(cur, change):
            value = change['value']
            path = change['path']

            if is_request(change['path']):
                parts = re.split(r"[\\/]", path)
                company = parts[2]
                user_id = parts[3].split("_")[0]

                value["company"] = company
                value["user_id"] = user_id
            if is_shift(change['path']):
                parts = re.split(r"[\\/]", path)
                company = parts[2]
                user_id = parts[3].split(".")[0]

                value["company"] = company
                value["user_id"] = user_id
            if is_task_config(change['path']) and is_task(change['source']):
                value['location'] = change['location']
                value['company'] = change['company']

            change['value'] = value

            route(cur, change)
        for change in changes:
            result = self.with_db(handle_change)
            if not result(change):
                continue

    def resolve_human_readable(self, cur, field, value):
        if not value:
            return "—"

        try:
            if field == "user_id":
                cur.execute("SELECT name FROM users WHERE id=%s", [value])
                row = cur.fetchone()
                return row[0] if row else value
            elif field == "company_id":
                cur.execute("SELECT name FROM companies WHERE id=%s", [value])
                row = cur.fetchone()
                return row[0] if row else value
            elif field == "location_id":
                cur.execute("SELECT address FROM locations WHERE id=%s", [value])
                row = cur.fetchone()
                return row[0] if row else value
            elif field == "task_id":
                cur.execute("SELECT name FROM tasks WHERE id=%s", [value])
                row = cur.fetchone()
                return row[0] if row else value
            elif field == "shift_id":
                cur.execute("""
                    SELECT u.name
                    FROM users u
                    JOIN company_user_relation cur ON cur.user_id = u.id
                    JOIN time_entries te ON te.company_user_relation_id = cur.id
                    WHERE te.id = %s
                """, [value])
                row = cur.fetchone()
                return row[0] if row else value
        except Exception:
            pass
        return value

def is_request(path):
    return 'requests' in path
def is_shift(path):
    return 'Fyrirtaeki' in path
def is_user(path):
    return 'users.json' in path
def is_task_config(path):
    return 'task_config.json' in path
def is_task(source):
    return source == 'task'
def is_location(source):
    return source == 'location'
def is_company(source):
    return source == 'company'

def route(cur, change):
    print("routing change...", change)

    
    path = change['path']
    operation = change['type']
    value = change['value']

    if is_request(path):
        add = requests.add_request
        delete = requests.delete_request
        edit = requests.edit_request
    elif is_shift(path):
        add = shifts.add_shift
        delete = shifts.delete_shift
        edit = shifts.edit_shift
    elif is_user(path):
        add = users.add_user
        delete = users.delete_user
        edit = users.update_user
    else:
        # is task_config
        source = change['source']
        if is_location(source):
            add = locations.add_location
            delete = locations.delete_location
            edit = locations.edit_location
        elif is_company(source):
            add = companies.add_company
            delete = companies.delete_company
            edit = companies.edit_company
        else:
            # is task
            add = tasks.add_task
            delete = tasks.delete_task
            edit = tasks.edit_task

    route_op(operation, value, cur, add, delete, edit)

def route_op(op, value, cur, add, delete, edit):
    """
    Routes to either add, delete or edit
    based on op.

    Used to generalize when dealing with different handlers between
    different implementations of these functions
    """
    if op == 'added':
        add(cur, value)
    if op == 'removed':
        delete(cur, value)
    if op == 'changed':
        edit(cur, value)

if __name__ == "__main__":
    outgoing = Outgoing()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting…")
