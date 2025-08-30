import threading
import time
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from watchdog.observers import Observer
from psycopg2.pool import SimpleConnectionPool
from lib.watcher import JSONChangeHandler
from apps.app import LOCATION

class Outgoing():
    def __init__(self):
        load_dotenv()

        self.pool = SimpleConnectionPool(1, 4, dsn=os.getenv("DATABASE_URL"), sslmode="require")

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
        self.observers.append(self.init_observer(self.with_db(self.users_callback), "Database/users.json"))
        self.observers.append(self.init_observer(self.with_db(self.tasks_callback), "Database/task_config.json"))
        self.observers.append(self.init_observer(self.with_db(self.shifts_callback), "Database/Fyrirtaeki"))
        self.observers.append(self.init_observer(self.with_db(self.requests_callback), "Database/requests"))

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
            except Exception as e:
                conn.rollback()
                print(f"DB error: {e}")
                return False
            finally:
                self.pool.putconn(conn)
        return wrapper

    def init_observer(self, callback, path):
        watcher = JSONChangeHandler(callback, path)
        observer = Observer()
        observer.schedule(watcher, path=path, recursive=True)
        observer.start()
        return (observer, watcher, path)

    def users_callback(self, cur, changes):
        def split_path(path):
            if len(path) == 0:
                return None, None
            else:
                return path[1], path[2]

        for change in changes:
            print(change)
            operation = change["type"]
            value = change["value"]
            if operation == "added":
                cur.execute("INSERT INTO users (id, name, pin) VALUES(%s, %s, %s)", 
                            [value["id"], value["name"], value["pin"]])

                cur.execute("SELECT id FROM companies WHERE name = %s", [value["company"]])
                company_id = cur.fetchone()
                if not company_id:
                    raise ValueError(f"Company '{value['company']}' does not exist")
                company_id = company_id[0]
                # todo! change to not in
                settings = {k: value[k] for k in ("commute_minutes", "lunch_minutes") if k in value}

                cur.execute("INSERT INTO company_user_relation (company_id, user_id, role, custom_settings) VALUES(%s, %s, %s, %s)", 
                                    [company_id, value["id"], "employee", psycopg2.extras.Json(settings)])
            if operation == "removed":
                cur.execute("DELETE FROM users WHERE id = %s", [value["id"]])
                cur.execute("DELETE FROM company_user_relation WHERE user_id = %s", [value["id"]])
            if operation == "changed":
                user_id, field = split_path(change["path"])
                if field:
                    # need to change company_user_relation too!!
                    cur.execute(f"UPDATE users SET {field}=%s WHERE id=%s", [value, user_id])

    def tasks_callback(self, cur, changes):
        def split_path(path):
            location = None
            company = None
            task_id = None
            field = None
            if len(path) == 2:
                location = path[1]
            if len(path) == 3:
                location = path[1]
                company = path[2]
            if len(path) > 3:
                location = path[1]
                company = path[2]
                task_id = path[3]
                field = path[4]
            return location, company, task_id, field

        for change in changes:
            print(change)
            operation = change["type"]
            value = change["value"]
            path = change["path"]
            location, company, task_id, field = split_path(path)
            if operation == "added":
                if location is not None and company is None:
                    # still need to account for if location and company are added while offline
                    cur.execute("INSERT INTO locations (address) VALUES (%s)", [location])
                if location is not None and company is not None:
                    def insert_task(task):
                        cur.execute("SELECT id FROM companies WHERE name=%s", [company])
                        company_id = cur.fetchone()[0]
                        cur.execute("SELECT id FROM locations WHERE address=%s", [location])
                        location_id = cur.fetchone()[0]
                        cur.execute("INSERT INTO tasks (id, name, company_id, location_id, completed) VALUES (%s, %s, %s, %s, %s)",
                                    [task["id"], task["name"], company_id, location_id, task["completed"]])
                    if isinstance(value, list):
                        cur.execute("INSERT INTO companies (name) VALUES (%s)", [company])
                        for task in value:
                            insert_task(task)
                    else:
                        insert_task(value)
            if operation == "removed":
                if location and company is None:
                    cur.execute("DELETE FROM locations WHERE address=%s", [location])
                if location and company:
                    if isinstance(value, list):
                        cur.execute("DELETE FROM companies WHERE name=%s", [company])
                        for task in value:
                            cur.execute("DELETE FROM tasks WHERE id=%s", [task["id"]])
                    else:
                        cur.execute("DELETE FROM tasks WHERE id=%s", [value["id"]])
            # THIS CURRENTLY ONLY HAPPENS WHEN TASKS IS CHANGED
            # IF LOCATION OR COMPANY CHANGES IT DELETES AND RE-ADDS, although it seems fine for now (except for location change, see above)
            if operation == "changed":
                if task_id:
                    cur.execute(f"UPDATE tasks SET {field}=%s WHERE id=%s", [value, task_id])


    def shifts_callback(self, cur, changes):
        def split_path(path):
            if len(path) == 0:
                company = None
                user_id = None
            else:
                company = path[0].split("/")[2]
                user_id = path[0].split("/")[3].split(".")[0]
            if len(path) == 2:
                shift_id = path[1]
            else:
                shift_id = None
            if len(path) > 2:
                shift_id = path[1]
                field = path[2]
            else:
                field = None
            return company, user_id, shift_id, field

        for change in changes:
            print(change)
            operation = change["type"]
            value = change["value"]
            path = change["path"]
            company, user_id, shift_id, field = split_path(path)
            if operation == "added":
                if field is None:
                    cur.execute("SELECT id FROM companies WHERE name=%s", [company])
                    company_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM company_user_relation WHERE company_id=%s AND user_id=%s",
                                [company_id, user_id])
                    company_user_relation_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM locations WHERE address=%s",
                                [value["location"]])
                    location_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM tasks WHERE name=%s AND company_id=%s AND location_id=%s",
                                [value["task"], company_id, location_id])
                    task_id = cur.fetchone()[0]
                    extra = {k: value[k] for k in value if k not in ("id", "task", "location", "clock_in", "clock_out")}

                    columns = ["id", "company_user_relation_id", "location_id", "task_id", "clock_in"]
                    placeholders = ["%s", "%s", "%s", "%s", "%s"]
                    new_entry = [
                        value["id"],
                        company_user_relation_id,
                        location_id,
                        task_id,
                        value["clock_in"],
                    ]

                    if "clock_out" in value:
                        columns.append("clock_out")
                        placeholders.append("%s")
                        new_entry.append(value["clock_out"])

                    columns.append("extra")
                    placeholders.append("%s")
                    new_entry.append(psycopg2.extras.Json(extra))

                    sql = f"""
                        INSERT INTO time_entries ({", ".join(columns)})
                        VALUES ({", ".join(placeholders)})
                    """

                    cur.execute(sql, new_entry)
                else:
                    if field in ("id", "task", "location", "clock_in", "clock_out"):
                        cur.execute(f"UPDATE time_entries SET {field}=%s WHERE id=%s", [value, shift_id])
                    else:
                        cur.execute("SELECT extra FROM time_entries WHERE id=%s", [shift_id])
                        extra = cur.fetchone()[0]
                        extra[field] = value
                        cur.execute("UPDATE time_entries SET extra=%s WHERE id=%s", [psycopg2.extras.Json(extra), shift_id])
            if operation == "removed":
                cur.execute("DELETE FROM time_entries WHERE id=%s", [value["id"]])
            if operation == "changed":
                if field == "location":
                    cur.execute("SELECT id FROM locations WHERE address=%s", [value])
                    location_id = cur.fetchone()[0]
                    cur.execute(f"UPDATE time_entries SET location_id=%s WHERE id=%s", [location_id, shift_id])
                elif field == "task":
                    cur.execute("SELECT location_id FROM time_entries WHERE id=%s", [shift_id])
                    location_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM companies WHERE name=%s", [company])
                    company_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM tasks WHERE name=%s AND location_id=%s AND company_id=%s",
                                [value, location_id, company_id])
                    task_id = cur.fetchone()[0]
                    cur.execute(f"UPDATE time_entries SET task_id=%s WHERE id=%s", [task_id, shift_id])
                else:
                    if field in ("id", "clock_in", "clock_out"):
                        cur.execute(f"UPDATE time_entries SET {field}=%s WHERE id=%s", [value, shift_id])
                    else:
                        cur.execute("SELECT extra FROM time_entries WHERE id=%s", [shift_id])
                        extra = cur.fetchone()[0]
                        extra[field] = value
                        cur.execute("UPDATE time_entries SET extra=%s WHERE id=%s", [psycopg2.extras.Json(extra), shift_id])


    def requests_callback(self, cur, changes):
        def split_path(path):
            if len(path) == 0:
                company = None
                user_id = None
            else:
                company = path[0].split("/")[2]
                user_id = path[0].split("/")[3].split("_")[0]
            if len(path) == 2:
                request_id = path[1]
            else:
                request_id = None
            if len(path) > 2:
                request_id = path[1]
                field = path[2]
            else:
                field = None
            return company, user_id, request_id, field

        for change in changes:
            operation = change["type"]
            print(change)
            value = change["value"]
            path = change["path"]
            company, user_id, request_id, field = split_path(path)
            if operation == "added":
                cur.execute("SELECT id FROM locations WHERE address=%s", [value["location"]])
                location_id = cur.fetchone()[0]
                cur.execute("SELECT id FROM companies WHERE name=%s", [value["company"]])
                company_id = cur.fetchone()[0]
                cur.execute("SELECT id FROM tasks WHERE name=%s AND location_id=%s AND company_id=%s",
                            [value["task"], location_id, company_id])
                task_id = cur.fetchone()[0]
                extra = {k: value[k] for k in value if k not in ("id", "task", "location", "company", "requested_start", "requested_end", "reason", "status")}
                cur.execute("""INSERT INTO requests 
                            (id, user_id, task_id, company_id, location_id, requested_start, requested_end, extra, reason, status)
                            VALUES 
                            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            [value["id"],
                             user_id,
                             task_id,
                             company_id,
                             location_id,
                             value["requested_start"],
                             value["requested_end"],
                             psycopg2.extras.Json(extra),
                             value["reason"],
                             value["status"]])
            if operation == "removed":
                cur.execute("DELETE FROM requests WHERE id=%s", [value["id"]])
            if operation == "changed":
                if field == "location":
                    cur.execute("SELECT id FROM locations WHERE address=%s", [value])
                    location_id = cur.fetchone()[0]
                    cur.execute("UPDATE requests SET location_id=%s WHERE id=%s", [location_id, request_id])
                elif field == "company":
                    cur.execute("SELECT id FROM companies WHERE name=%s", [value])
                    company_id = cur.fetchone()[0]
                    cur.execute("UPDATE requests SET company_id=%s WHERE id=%s", [company_id, request_id])
                elif field == "task":
                    cur.execute("SELECT location_id FROM requests WHERE id=%s", [request_id])
                    location_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM companies WHERE name=%s", [company])
                    company_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM tasks WHERE name=%s AND location_id=%s AND company_id=%s",
                                [value, location_id, company_id])
                    task_id = cur.fetchone()[0]
                    cur.execute(f"UPDATE requests SET task_id=%s WHERE id=%s", [task_id, request_id])
                else:
                    if field in ("id", "requested_start", "requested_end", "status", "reason"):
                        cur.execute(f"UPDATE requests SET {field}=%s WHERE id=%s", [value, request_id])
                    else:
                        cur.execute("SELECT extra FROM requests WHERE id=%s", [request_id])
                        extra = cur.fetchone()[0]
                        extra[field] = value
                        cur.execute("UPDATE requests SET extra=%s WHERE id=%s", [psycopg2.extras.Json(extra), request_id])

if __name__ == "__main__":
    outgoing = Outgoing()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting…")
