import threading
import tempfile
import json
import os
import psycopg2
import select
import time
from dotenv import load_dotenv
from apps.app import LOCATION

class Incoming():
    def __init__(self, outgoing):
        self.outgoing = outgoing
        load_dotenv()

        self.conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
        self.conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        self.cur = self.conn.cursor()
        self.cur.execute("LISTEN requests_channel;")
        self._start()
        print("Listening on requests_channel...")

    def _start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        while True:
            if select.select([self.conn], [], [], 5) == ([], [], []):
                # no event in 5 seconds
                continue
            self.conn.poll()
            while self.conn.notifies:
                notify = self.conn.notifies.pop(0)
                payload = json.loads(notify.payload)
                if payload["source"] == LOCATION:
                    continue
                print("Got NOTIFY:", notify.payload)
                if payload["table"] == "users":
                    self.handle_users(payload)
                if payload["table"] == "companies":
                    self.handle_companies(payload)
                if payload["table"] == "locations":
                    self.handle_locations(payload)
                if payload["table"] == "company_user_relation":
                    self.handle_company_user_relation(payload)
                if payload["table"] == "requests":
                    self.handle_requests(payload)
                if payload["table"] == "tasks":
                    self.handle_tasks(payload)
                if payload["table"] == "time_entries":
                    self.handle_shifts(payload)

    def write_to_file(self, procedure, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []

        procedure(data)

        dir_name = os.path.dirname(path) or "."
        os.makedirs(dir_name, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tmp_file:
            json.dump(data, tmp_file, indent=4, ensure_ascii=False)
            temp_path = tmp_file.name

        self.outgoing.lock_file(path)
        os.replace(temp_path, path)
        self.outgoing.unlock_file(path, data)

    def handle_users(self, payload):
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            new_user = {
                "id": new["id"],
                "name": new["name"],
                "pin": new["pin"]
            }

            def procedure(data):
                data.append(new_user)
        elif action == "DELETE":
            old = payload["old"]
            def procedure(data):
                data[:] = [d for d in data if d["id"] != old["id"]]
        else:
            old = payload["old"]
            new = payload["new"]

            def procedure(data):
                for i, d in enumerate(data):
                    if d["id"] == old["id"]:
                        data[i] = new
                        break

        self.write_to_file(procedure, "Database/users.json")

    def handle_company_user_relation(self, payload):
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            self.cur.execute("SELECT name FROM companies WHERE id=%s", [new["company_id"]])
            company = self.cur.fetchone()[0]

            def procedure(data):
                for i, d in enumerate(data):
                    if d["id"] == new["user_id"]:
                        data[i]["company"] = company
                        for i2, d2 in new["custom_settings"].items():
                            data[i][i2] = d2

        elif action == "DELETE":
            def procedure(data):
                return
        else:
            # assume company_id never changes, just adds a new one, so custom_settings only changes
            new = payload["new"]

            def procedure(data):
                for i, d in enumerate(data):
                    if d["id"] == new["user_id"]:
                        for i2, d2 in new["custom_settings"].items():
                            data[i][i2] = d2

        self.write_to_file(procedure, "Database/users.json")

    def handle_companies(self, payload):
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            def procedure(data):
                for _, loc in data.items():
                    if new["name"] not in loc:
                        loc[new["name"]] = []

        elif action == "DELETE":
            old = payload["old"]
            def procedure(data):
                for _, loc in data.items():
                    del loc[old["name"]]
        else:
            old = payload["old"]
            new = payload["new"]

            def procedure(data):
                for _, loc in data.items():
                    if old["name"] in loc:
                        loc[new["name"]] = loc.pop(old["name"])

        self.write_to_file(procedure, "Database/task_config.json")

    def handle_locations(self, payload):
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            def procedure(data):
                data[new["address"]] = {}

        elif action == "DELETE":
            old = payload["old"]
            def procedure(data):
                del data[old["address"]]

        else:
            old = payload["old"]
            new = payload["new"]

            def procedure(data):
                if old["address"] in data:
                    data[new["address"]] = data.pop(old["address"])

        self.write_to_file(procedure, "Database/task_config.json")

    def handle_requests(self, payload):
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            company_id = new["company_id"]
            task_id = new["task_id"]
            location_id = new["location_id"]
            self.cur.execute("SELECT name FROM companies WHERE id=%s", [company_id])
            company = self.cur.fetchone()[0]
            self.cur.execute("SELECT name FROM tasks WHERE id=%s", [task_id])
            task = self.cur.fetchone()[0]
            self.cur.execute("SELECT address FROM locations WHERE id=%s", [location_id])
            location = self.cur.fetchone()[0]
            user_id = new["user_id"]
            new_request = {
                "id": new["id"],
                "task": task,
                "location": location,
                "company": company,
                "requested_start": new["requested_start"],
                "requested_end": new["requested_end"],
                "reason": new["reason"],
                "status": new["status"]
            }
            for field, value in new["extra"].items():
                new_request[field] = value
            def procedure(data):
                data.append(new_request)

        elif action == "DELETE":
            old = payload["old"]
            company_id = old["company_id"]
            self.cur.execute("SELECT name FROM companies WHERE id=%s", [company_id])
            company = self.cur.fetchone()[0]
            user_id = old["user_id"]
            def procedure(data):
                data[:] = [d for d in data if d["id"] != old["id"]]

        else:
            old = payload["old"]
            new = payload["new"]
            company_id = new["company_id"]
            task_id = new["task_id"]
            location_id = new["location_id"]
            self.cur.execute("SELECT name FROM companies WHERE id=%s", [company_id])
            company = self.cur.fetchone()[0]
            self.cur.execute("SELECT name FROM tasks WHERE id=%s", [task_id])
            task = self.cur.fetchone()[0]
            self.cur.execute("SELECT address FROM locations WHERE id=%s", [location_id])
            location = self.cur.fetchone()[0]
            user_id = new["user_id"]
            new_request = {
                "id": new["id"],
                "task": task,
                "location": location,
                "company": company,
                "requested_start": new["requested_start"],
                "requested_end": new["requested_end"],
                "reason": new["reason"],
                "status": new["status"]
            }
            for field, value in new["extra"].items():
                new_request[field] = value

            def procedure(data):
                for d in data:
                    if d["id"] == new["id"]:
                        d.update(new_request)

        self.write_to_file(procedure, f"Database/requests/{company}/{user_id}_requests.json")

    def handle_tasks(self, payload):
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            new_task = {
                "id": new["id"],
                "name": new["name"],
                "completed": new["completed"]
            }
            company_id = new["company_id"]
            location_id = new["location_id"]
            self.cur.execute("SELECT name FROM companies WHERE id=%s", [company_id])
            company = self.cur.fetchone()[0]
            self.cur.execute("SELECT address FROM locations WHERE id=%s", [location_id])
            location = self.cur.fetchone()[0]

            def procedure(data):
                data[location][company].append(new_task)

        elif action == "DELETE":
            old = payload["old"]
            company_id = old["company_id"]
            location_id = old["location_id"]
            self.cur.execute("SELECT name FROM companies WHERE id=%s", [company_id])
            company = self.cur.fetchone()[0]
            self.cur.execute("SELECT address FROM locations WHERE id=%s", [location_id])
            location = self.cur.fetchone()[0]
            def procedure(data):
                data[location][company][:] = [d for d in data[location][company] if d["id"] != old["id"]]

        else:
            old = payload["old"]
            new = payload["new"]
            old_company_id = old["company_id"]
            old_location_id = old["location_id"]
            self.cur.execute("SELECT name FROM companies WHERE id=%s", [old_company_id])
            old_company = self.cur.fetchone()[0]
            self.cur.execute("SELECT address FROM locations WHERE id=%s", [old_location_id])
            old_location = self.cur.fetchone()[0]

            new_company_id = new["company_id"]
            new_location_id = new["location_id"]
            self.cur.execute("SELECT name FROM companies WHERE id=%s", [new_company_id])
            new_company = self.cur.fetchone()[0]
            self.cur.execute("SELECT address FROM locations WHERE id=%s", [new_location_id])
            new_location = self.cur.fetchone()[0]

            new_task = {
                "id": new["id"],
                "name": new["name"],
                "completed": new["completed"]
            }

            def procedure(data):
                data[old_location][old_company][:] = [d for d in data[old_location][old_company] if d["id"] != old["id"]]
                data[new_location][new_company].append(new_task)

        self.write_to_file(procedure, "Database/task_config.json")

    def handle_shifts(self, payload):
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            company_user_id = new["company_user_relation_id"]
            self.cur.execute("SELECT company_id, user_id FROM company_user_relation WHERE id=%s", [company_user_id])
            company_id, user_id = self.cur.fetchone()

            task_id = new["task_id"]
            location_id = new["location_id"]

            self.cur.execute("SELECT name FROM companies WHERE id=%s", [company_id])
            company = self.cur.fetchone()[0]
            self.cur.execute("SELECT name FROM tasks WHERE id=%s", [task_id])
            task = self.cur.fetchone()[0]
            self.cur.execute("SELECT address FROM locations WHERE id=%s", [location_id])
            location = self.cur.fetchone()[0]

            new_shift = {
                "id": new["id"],
                "task": task,
                "location": location,
                "clock_in": new["clock_in"]
            }

            if "clock_out" in new.keys():
                new_shift["clock_out"] = new["clock_out"]

            for field, value in new["extra"].items():
                new_shift[field] = value

            def procedure(data):
                data.append(new_shift)

        elif action == "DELETE":
            old = payload["old"]
            company_user_id = old["company_user_relation_id"]
            self.cur.execute("SELECT user_id, company_id FROM company_user_relation WHERE id=%s", [company_user_id])
            user_id, company_id = self.cur.fetchone()
            self.cur.execute("SELECT name FROM companies WHERE id=%s", [company_id])
            company = self.cur.fetchone()[0]

            def procedure(data):
                data[:] = [d for d in data if d["id"] != old["id"]]

        else:
            old = payload["old"]
            new = payload["new"]
            company_user_id = new["company_user_relation_id"]
            self.cur.execute("SELECT company_id, user_id FROM company_user_relation WHERE id=%s", [company_user_id])
            company_id, user_id = self.cur.fetchone()

            task_id = new["task_id"]
            location_id = new["location_id"]

            self.cur.execute("SELECT name FROM companies WHERE id=%s", [company_id])
            company = self.cur.fetchone()[0]
            self.cur.execute("SELECT name FROM tasks WHERE id=%s", [task_id])
            task = self.cur.fetchone()[0]
            self.cur.execute("SELECT address FROM locations WHERE id=%s", [location_id])
            location = self.cur.fetchone()[0]

            new_shift = {
                "id": new["id"],
                "task": task,
                "location": location,
                "clock_in": new["clock_in"]
            }
            if "clock_out" in new.keys():
                new_shift["clock_out"] = new["clock_out"]
            for field, value in new["extra"].items():
                new_shift[field] = value


            def procedure(data):
                for d in data:
                    if d["id"] == new["id"]:
                        d.update(new_shift)

        self.write_to_file(procedure, f"Database/Fyrirtaeki/{company}/{user_id}.json")

class ListenerThread:
    def __init__(self, dsn, channels, on_notify):
        self.dsn = dsn                 # e.g. "dbname=... user=... password=... host=... port=..."
        self.channels = list(channels) # ["shift_updates", ...]
        self.on_notify = on_notify     # callback(payload, channel)
        self._running = True
        self.conn = None
        self.cur = None

    def stop(self):
        self._running = False
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass

    def _connect(self):
        # per-thread connection, autocommit, keepalives
        self.conn = psycopg2.connect(
            self.dsn,
            keepalives=1,
            keepalives_idle=30,      # seconds
            keepalives_interval=10,  # seconds
            keepalives_count=3
        )
        self.conn.set_session(autocommit=True)
        self.cur = self.conn.cursor()
        for ch in self.channels:
            self.cur.execute(f'LISTEN "{ch}";')

    def _loop_once(self, timeout=30.0):
        # Wait for socket readability or timeout, then poll
        fileno = self.conn.fileno()
        # On Windows, select() works with sockets; psycopg2 uses sockets internally
        r, _, _ = select.select([fileno], [], [], timeout)
        if r:
            self.conn.poll()
            while self.conn.notifies:
                note = self.conn.notifies.pop(0)
                # note.payload, note.channel
                try:
                    self.on_notify(note.payload, note.channel)
                except Exception as e:
                    # don’t crash the thread on bad callback
                    print(f"[notify-error] {e}")

    def _run(self):
        backoff = 1.0
        while self._running:
            try:
                if not self.conn:
                    self._connect()
                    backoff = 1.0  # reset backoff on successful connect
                self._loop_once(timeout=30.0)
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                print(f"[db] connection lost: {e}")
                try:
                    if self.conn:
                        self.conn.close()
                except Exception:
                    pass
                self.conn = None
                self.cur = None
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)  # capped exponential backoff
            except Exception as e:
                # Non-DB exceptions shouldn't permanently kill the loop
                print(f"[listener] unexpected error: {e}")
                time.sleep(1.0)

    # spawn with threading.Thread(target=listener._run, daemon=True).start()