import threading
import tempfile
import json
import os
import psycopg2
import select
import time
from dotenv import load_dotenv
from apps.app import LOCATION
from lib.lib import resolve_from_row, read, update_last_sync
from postgres.api.companies import add_local_company, delete_local_company, edit_local_company
from postgres.api.locations import add_local_location, delete_local_location, edit_local_location
from postgres.api.requests import add_local_request, delete_local_request, edit_local_request
from postgres.api.shifts import add_local_shift, delete_local_shift, edit_local_shift
from postgres.api.tasks import add_local_task, delete_local_task, edit_local_task
from postgres.api.users import add_local_contract, add_local_user, delete_local_user, edit_local_contract, edit_local_user

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
                update_last_sync()
                print("Got NOTIFY:", notify.payload)
                table = payload["table"]
                if table == "users":
                    path = "Database/users.json"
                    self.handle_users(payload, path)
                if table == "companies":
                    path = "Database/task_config.json"
                    self.handle_companies(payload, path)
                if table == "locations":
                    path = "Database/task_config.json"
                    self.handle_locations(payload, path)
                if table == "contracts":
                    path = "Database/users.json"
                    self.handle_contracts(payload, path)
                if table == "tasks":
                    path = "Database/users.json"
                    self.handle_tasks(payload, path)
                if table == "requests":
                    user_id, company = resolve_from_row(
                            payload["new"] or payload["old"], self.cur)
                    path = f"Database/requests/{company}/{user_id}_requests.json"
                    self.handle_requests(payload, path)
                if table == "shifts":
                    user_id, company = resolve_from_row(
                            payload["new"] or payload["old"], self.cur)
                    path = f"Database/Fyrirtaeki/{company}/{user_id}.json"
                    self.handle_shifts(payload, path)

    def write_to_file(self, data, path):
        dir_name = os.path.dirname(path) or "."
        os.makedirs(dir_name, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tmp_file:
            json.dump(data, tmp_file, indent=4, ensure_ascii=False)
            temp_path = tmp_file.name

        self.outgoing.lock_file(path)
        os.replace(temp_path, path)
        self.outgoing.unlock_file(path, data)

    def handle_users(self, payload, path):
        data = read(path)
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            add_local_user(new, data, self.cur)
        elif action == "DELETE":
            old = payload["old"]
            delete_local_user(old, data, self.cur)
        else:
            old = payload["old"]
            new = payload["new"]

            edit_local_user(old, new, data, self.cur)

        self.write_to_file(data, path)

    def handle_contracts(self, payload, path):
        data = read(path)
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            add_local_contract(new, data)
        elif action == "DELETE":
            return
        else:
            new = payload["new"]
            edit_local_contract(new, data)

        self.write_to_file(data, path)

    def handle_companies(self, payload, path):
        data = read(path)
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            add_local_company(new, data)

        elif action == "DELETE":
            old = payload["old"]
            delete_local_company(old, data)
        else:
            old = payload["old"]
            new = payload["new"]
            edit_local_company(old, new, data)

        self.write_to_file(data, path)

    def handle_locations(self, payload, path):
        data = read(path)
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            add_local_location(new, data, self.cur)

        elif action == "DELETE":
            old = payload["old"]
            delete_local_location(old, data)

        else:
            old = payload["old"]
            new = payload["new"]
            edit_local_location(old, new, data)

        self.write_to_file(data, path)

    def handle_requests(self, payload, path):
        data = read(path)
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            add_local_request(new, data, self.cur)

        elif action == "DELETE":
            old = payload["old"]
            delete_local_request(old, data)

        else:
            new = payload["new"]
            edit_local_request(new, data, self.cur)

        self.write_to_file(data, path)

    def handle_tasks(self, payload, path):
        data = read(path)
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            add_local_task(new, data)

        elif action == "DELETE":
            old = payload["old"]
            delete_local_task(old, data)

        else:
            old = payload["old"]
            new = payload["new"]
            edit_local_task(old, new, data)

        self.write_to_file(data, path)

    def handle_shifts(self, payload, path):
        data = read(path)
        action = payload["action"]
        if action == "INSERT":
            new = payload["new"]
            add_local_shift(new, data, self.cur)

        elif action == "DELETE":
            old = payload["old"]
            delete_local_shift(old, data, self.cur)

        else:
            new = payload["new"]
            edit_local_shift(new, data, self.cur)

        self.write_to_file(data, path)

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
