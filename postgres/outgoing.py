import threading
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

    def users_callback(self, cur, changes):
        def split_path(path):
            if len(path) == 0:
                return None, None
            else:
                return path[1], path[2]

        for change in changes:
            operation = change["type"]
            value = change["value"]

            if operation == "added":
                # Insert user
                cur.execute(
                    "INSERT INTO users (id, name, pin) VALUES(%s, %s, %s)",
                    [value["id"], value["name"], value["pin"]]
                )

                # Get company id
                cur.execute("SELECT id FROM companies WHERE name = %s", [value["company"]])
                company_id = cur.fetchone()
                if not company_id:
                    raise ValueError(f"Company '{value['company']}' does not exist")
                company_id = company_id[0]

                # Prepare settings
                settings = {k: value[k] for k in value if k not in ("id", "name", "company", "pin")}
                cur.execute(
                    "INSERT INTO company_user_relation (company_id, user_id, role, custom_settings) VALUES(%s, %s, %s, %s)",
                    [company_id, value["id"], "employee", psycopg2.extras.Json(settings)]
                )

                # Rich Table
                table = Table(box=box.ROUNDED, show_lines=True)
                table.add_column("Field", style="cyan", no_wrap=True)
                table.add_column("Value", style="magenta")

                table.add_row("User Name", value["name"])
                table.add_row("Pin", str(value["pin"]))
                table.add_row("Company", value["company"])
                table.add_row("Settings", str(settings))

                self.console.print("[bold green]✅ User added successfully![/bold green]")
                self.console.print(table)

            elif operation == "removed":
                cur.execute("DELETE FROM users WHERE id = %s", [value["id"]])
                cur.execute("DELETE FROM company_user_relation WHERE user_id = %s", [value["id"]])

                table = Table(box=box.ROUNDED, show_lines=True)
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="magenta")

                table.add_row("User Name", value.get("name", "Unknown"))
                table.add_row("Pin", str(value.get("pin", "Unknown")))
                table.add_row("Company", value.get("company", "Unknown"))

                self.console.print("[bold red]🗑️ User removed:[/bold red]")
                self.console.print(table)

            elif operation == "changed":
                user_id, field = split_path(change["path"])
                # need to change user_company_relation too!!!
                if field in ("name", "pin"):
                    cur.execute(f"UPDATE users SET {field}=%s WHERE id=%s", [value, user_id])
                elif field:
                    cur.execute("SELECT custom_settings FROM company_user_relation WHERE user_id=%s", [user_id])
                    custom_settings = cur.fetchone()[0]
                    custom_settings[field] = value
                    cur.execute("UPDATE company_user_relation SET custom_settings=%s WHERE user_id=%s", [psycopg2.extras.Json(custom_settings), user_id])
                if field:
                    table = Table(box=box.ROUNDED, show_lines=True)
                    table.add_column("Field", style="cyan")
                    table.add_column("New Value", style="magenta")
                    table.add_row(field, str(value))

                    self.console.print("[bold yellow]✏️ User updated:[/bold yellow]")
                    self.console.print(table)

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
            operation = change["type"]
            value = change["value"]
            path = change["path"]
            location, company, task_id, field = split_path(path)

            if operation == "added":
                if location is not None and company is None:
                    # New location
                    cur.execute("INSERT INTO locations (address) VALUES (%s)", [location])
                    table = Table(box=box.ROUNDED)
                    table.add_column("Field", style="cyan")
                    table.add_column("Value", style="magenta")
                    table.add_row("Location", location)
                    self.console.print("[bold green]✅ Location added![/bold green]")
                    self.console.print(table)

                if location is not None and company is not None:
                    # New company + tasks
                    def insert_task(task):
                        cur.execute("SELECT id FROM companies WHERE name=%s", [company])
                        company_id = cur.fetchone()[0]
                        cur.execute("SELECT id FROM locations WHERE address=%s", [location])
                        location_id = cur.fetchone()[0]
                        cur.execute(
                            "INSERT INTO tasks (id, name, company_id, location_id, completed) VALUES (%s, %s, %s, %s, %s)",
                            [task["id"], task["name"], company_id, location_id, task.get("completed", False)]
                        )
                        table = Table(box=box.ROUNDED)
                        table.add_column("Field", style="cyan")
                        table.add_column("Value", style="magenta")
                        table.add_row("Task Name", task["name"])
                        table.add_row("Company", company)
                        table.add_row("Location", location)
                        table.add_row("Completed", str(task.get("completed", False)))
                        self.console.print("[bold green]✅ Task added![/bold green]")
                        self.console.print(table)

                    if isinstance(value, list):
                        cur.execute("INSERT INTO companies (name) VALUES (%s)", [company])
                        table = Table(box=box.ROUNDED)
                        table.add_column("Field", style="cyan")
                        table.add_column("Value", style="magenta")
                        table.add_row("Company Name", company)
                        self.console.print("[bold green]✅ Company added![/bold green]")
                        self.console.print(table)
                        for task in value:
                            insert_task(task)
                    else:
                        insert_task(value)

            elif operation == "removed":
                if location and company is None:
                    cur.execute("DELETE FROM locations WHERE address=%s", [location])
                    table = Table(box=box.ROUNDED)
                    table.add_column("Field", style="cyan")
                    table.add_column("Value", style="magenta")
                    table.add_row("Location", location)
                    self.console.print("[bold red]🗑️ Location removed:[/bold red]")
                    self.console.print(table)

                if location and company:
                    if isinstance(value, list):
                        cur.execute("DELETE FROM companies WHERE name=%s", [company])
                        table = Table(box=box.ROUNDED)
                        table.add_column("Field", style="cyan")
                        table.add_column("Value", style="magenta")
                        table.add_row("Company Name", company)
                        self.console.print("[bold red]🗑️ Company removed:[/bold red]")
                        self.console.print(table)
                        for task in value:
                            cur.execute("DELETE FROM tasks WHERE id=%s", [task["id"]])
                            table = Table(box=box.ROUNDED)
                            table.add_column("Field", style="cyan")
                            table.add_column("Value", style="magenta")
                            table.add_row("Task Name", task["name"])
                            table.add_row("Company", company)
                            table.add_row("Location", location)
                            self.console.print("[bold red]🗑️ Task removed:[/bold red]")
                            self.console.print(table)
                    else:
                        cur.execute("DELETE FROM tasks WHERE id=%s", [value["id"]])
                        table = Table(box=box.ROUNDED)
                        table.add_column("Field", style="cyan")
                        table.add_column("Value", style="magenta")
                        table.add_row("Task Name", value["name"])
                        table.add_row("Company", company)
                        table.add_row("Location", location)
                        self.console.print("[bold red]🗑️ Task removed:[/bold red]")
                        self.console.print(table)

            elif operation == "changed":
                if task_id:
                    cur.execute(f"UPDATE tasks SET {field}=%s WHERE id=%s", [value, task_id])
                    table = Table(box=box.ROUNDED)
                    table.add_column("Field", style="cyan")
                    table.add_column("New Value", style="magenta")
                    table.add_row(field, str(value))
                    self.console.print("[bold yellow]✏️ Task updated:[/bold yellow]")
                    self.console.print(table)


    def shifts_callback(self, cur, changes):
        import re
        import psycopg2.extras

        def split_path(path):
            if len(path) == 0:
                company = None
                user_id = None
            else:
                parts = re.split(r"[\\/]", path[0])
                company = parts[2] if len(parts) > 2 else None
                user_id = parts[3].split(".")[0] if len(parts) > 3 else None

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
            operation = change["type"]
            value = change["value"]
            path = change["path"]
            company, user_id, shift_id, field = split_path(path)

            if operation == "added":
                if field is None:
                    # New shift entry
                    cur.execute("SELECT id FROM companies WHERE name=%s", [company])
                    company_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM company_user_relation WHERE company_id=%s AND user_id=%s",
                                [company_id, user_id])
                    company_user_relation_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM locations WHERE address=%s", [value["location"]])
                    location_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM tasks WHERE name=%s AND company_id=%s AND location_id=%s",
                                [value["task"], company_id, location_id])
                    task_id = cur.fetchone()[0]
                    extra = {k: value[k] for k in value if k not in ("id", "task", "location", "clock_in", "clock_out")}

                    columns = ["id", "company_user_relation_id", "location_id", "task_id", "clock_in"]
                    placeholders = ["%s"] * len(columns)
                    new_entry = [value["id"], company_user_relation_id, location_id, task_id, value["clock_in"]]

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

                    # Rich table display
                    table = Table(box=box.ROUNDED)
                    table.add_column("Field", style="cyan")
                    table.add_column("Value", style="magenta")
                    table.add_row("Shift owner", self.resolve_human_readable(cur, "user_id", user_id))
                    table.add_row("Company", company)
                    table.add_row("Location", value["location"])
                    table.add_row("Task", value["task"])
                    table.add_row("Clock In", value["clock_in"])
                    table.add_row("Clock Out", value.get("clock_out", "—"))
                    table.add_row("Extra", str(extra))
                    self.console.print("[bold green]✅ Shift added![/bold green]")
                    self.console.print(table)

                else:
                    # Updating a field directly
                    if field in ("id", "task", "location", "clock_in", "clock_out"):
                        cur.execute(f"UPDATE time_entries SET {field}=%s WHERE id=%s", [value, shift_id])
                    else:
                        cur.execute("SELECT extra FROM time_entries WHERE id=%s", [shift_id])
                        extra = cur.fetchone()[0]
                        extra[field] = value
                        cur.execute("UPDATE time_entries SET extra=%s WHERE id=%s",
                                    [psycopg2.extras.Json(extra), shift_id])
                    table = Table(box=box.ROUNDED)
                    table.add_column("Field", style="cyan")
                    table.add_column("Value", style="magenta")
                    table.add_row("Shift owner", self.resolve_human_readable(cur, "shift_id", shift_id))
                    table.add_row(field, str(value))
                    self.console.print("[bold green]✅ Shift changed![/bold green]")
                    self.console.print(table)

            elif operation == "removed":
                cur.execute("DELETE FROM time_entries WHERE id=%s", [value["id"]])
                table = Table(box=box.ROUNDED)
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="magenta")
                table.add_row("Shift owner", self.resolve_human_readable(cur, "user_id", user_id))
                table.add_row("Company", company)
                table.add_row("Task", value.get("task", "—"))
                self.console.print("[bold red]🗑️ Shift removed:[/bold red]")
                self.console.print(table)

            elif operation == "changed":
                if field == "location":
                    cur.execute("SELECT id FROM locations WHERE address=%s", [value])
                    location_id = cur.fetchone()[0]
                    cur.execute("UPDATE time_entries SET location_id=%s WHERE id=%s", [location_id, shift_id])
                elif field == "task":
                    cur.execute("SELECT location_id FROM time_entries WHERE id=%s", [shift_id])
                    location_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM companies WHERE name=%s", [company])
                    company_id = cur.fetchone()[0]
                    cur.execute("SELECT id FROM tasks WHERE name=%s AND location_id=%s AND company_id=%s",
                                [value, location_id, company_id])
                    task_id = cur.fetchone()[0]
                    cur.execute("UPDATE time_entries SET task_id=%s WHERE id=%s", [task_id, shift_id])
                else:
                    if field in ("id", "clock_in", "clock_out"):
                        cur.execute(f"UPDATE time_entries SET {field}=%s WHERE id=%s", [value, shift_id])
                    else:
                        cur.execute("SELECT extra FROM time_entries WHERE id=%s", [shift_id])
                        extra = cur.fetchone()[0]
                        extra[field] = value
                        cur.execute("UPDATE time_entries SET extra=%s WHERE id=%s", [psycopg2.extras.Json(extra), shift_id])

                table = Table(box=box.ROUNDED)
                table.add_column("Field", style="cyan")
                table.add_column("New Value", style="magenta")
                table.add_row("Shift owner", self.resolve_human_readable(cur, "shift_id", shift_id))
                table.add_row(field, str(value))
                self.console.print("[bold yellow]✏️ Shift updated:[/bold yellow]")
                self.console.print(table)

    def requests_callback(self, cur, changes):
        def split_path(path):
            if len(path) == 0:
                company = None
                user_id = None
            else:
                parts = re.split(r"[\\/]", path[0])
                company = parts[2] if len(parts) > 2 else None
                user_id = parts[3].split("_")[0] if len(parts) > 3 else None

            request_id = path[1] if len(path) >= 2 else None
            field = path[2] if len(path) > 2 else None
            return company, user_id, request_id, field

        for change in changes:
            operation = change["type"]
            value = change["value"]
            path = change["path"]
            company, user_id, request_id, field = split_path(path)

            if operation == "added":
                # Fetch related IDs
                cur.execute("SELECT id FROM locations WHERE address=%s", [value["location"]])
                location_id = cur.fetchone()[0]
                cur.execute("SELECT id FROM companies WHERE name=%s", [value["company"]])
                company_id = cur.fetchone()[0]
                cur.execute("SELECT id FROM tasks WHERE name=%s AND location_id=%s AND company_id=%s",
                            [value["task"], location_id, company_id])
                task_id = cur.fetchone()[0]

                extra = {k: value[k] for k in value if k not in 
                         ("id", "task", "location", "company", "requested_start", "requested_end", "reason", "status")}

                # Insert into DB
                cur.execute("""INSERT INTO requests 
                            (id, user_id, task_id, company_id, location_id, requested_start, requested_end, extra, reason, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            [value["id"], user_id, task_id, company_id, location_id,
                             value["requested_start"], value["requested_end"],
                             psycopg2.extras.Json(extra), value["reason"], value["status"]])

                # Rich table display
                table = Table(box=box.ROUNDED)
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="magenta")
                table.add_row("Request", self.resolve_human_readable(cur, "request_id", value["id"]))
                table.add_row("User", self.resolve_human_readable(cur, "user_id", user_id))
                table.add_row("Company", value["company"])
                table.add_row("Location", value["location"])
                table.add_row("Task", value["task"])
                table.add_row("Requested Start", value["requested_start"])
                table.add_row("Requested End", value["requested_end"])
                table.add_row("Reason", value.get("reason", "—"))
                table.add_row("Status", value.get("status", "—"))
                table.add_row("Extra", str(extra))
                self.console.print("[bold green]✅ Request added![/bold green]")
                self.console.print(table)

            elif operation == "removed":
                cur.execute("DELETE FROM requests WHERE id=%s", [value["id"]])

                table = Table(box=box.ROUNDED)
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="magenta")
                table.add_row("Request", self.resolve_human_readable(cur, "request_id", value["id"]))
                table.add_row("User", self.resolve_human_readable(cur, "user_id", user_id))
                table.add_row("Company", company)
                table.add_row("Task", value.get("task", "—"))
                self.console.print("[bold red]🗑️ Request removed:[/bold red]")
                self.console.print(table)

            elif operation == "changed":
                # Update specific field
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
                    cur.execute("UPDATE requests SET task_id=%s WHERE id=%s", [task_id, request_id])
                else:
                    if field in ("id", "requested_start", "requested_end", "status", "reason"):
                        cur.execute(f"UPDATE requests SET {field}=%s WHERE id=%s", [value, request_id])
                    else:
                        cur.execute("SELECT extra FROM requests WHERE id=%s", [request_id])
                        extra = cur.fetchone()[0]
                        extra[field] = value
                        cur.execute("UPDATE requests SET extra=%s WHERE id=%s", [psycopg2.extras.Json(extra), request_id])

                table = Table(box=box.ROUNDED)
                table.add_column("Field", style="cyan")
                table.add_column("New Value", style="magenta")
                table.add_row(field, str(value))
                self.console.print("[bold yellow]✏️ Request updated:[/bold yellow]")
                self.console.print(table)

if __name__ == "__main__":
    outgoing = Outgoing()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting…")
