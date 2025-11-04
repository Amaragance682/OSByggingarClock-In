from datetime import datetime
import copy
import json
import os
from pathlib import Path
import tempfile
from threading import local
from typing import Dict
from apps.app import LOCATION
from lib.lib import load_cache
from lib.watcher import _load_json
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

from postgres.api import requests
from postgres.api.companies import add_company, add_local_company, delete_local_company, edit_local_company
from postgres.api.locations import add_local_location, add_location, delete_local_location, edit_local_location
from postgres.api.requests import add_local_request, add_request, delete_local_request, edit_local_request
from postgres.api.shifts import add_local_shift, add_shift, delete_local_shift, edit_local_shift
from postgres.api.tasks import add_local_task, add_task, delete_local_task, edit_local_task
from postgres.api.users import add_local_contract, add_local_user, add_user, delete_local_user, edit_local_contract, edit_local_user, update_user


class Merge():
    def __init__(self):
        load_dotenv()
        try:
            self.last_sync = datetime.fromisoformat(
                load_cache()["last_sync"])
            print(self.last_sync)
        except Exception:
            self.last_sync = datetime(1970, 1, 1)

        self.conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')

        local_data = _load_json("Database/")
        if local_data == None:
            raise RuntimeError("Loading local data failed / no local data to load!")

        task_config_data: Dict = local_data["Database/task_config.json"]
        users_data = local_data["Database/users.json"]
        shifts_data = [
            {
                **shift,
                "company": path.split("/")[2],
                "user_id": path.split("/")[3].split(".")[0]
            }
            for path, file in local_data.items()
            if "Fyrirtaeki" in path
            for shift in file]
        requests_data = [
            {
                **request,
                "company": path.split("/")[2],
                "user_id": path.split("/")[3].split("_")[0]
            }
            for path, file in local_data.items()
            if "requests" in path
            for request in file]

        self.cur = self.conn.cursor()
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute("SELECT * FROM companies")
            companies = cur.fetchall()
            cur.execute("SELECT * FROM locations")
            locations = cur.fetchall()
            cur.execute("SELECT * FROM users")
            users = cur.fetchall()
            cur.execute("SELECT * FROM contracts")
            contracts = cur.fetchall()
            cur.execute("SELECT * FROM tasks")
            tasks = cur.fetchall()
            cur.execute("SELECT * FROM shifts")
            shifts = cur.fetchall()
            cur.execute("SELECT * FROM requests")
            requests = cur.fetchall()


        locations_local = copy.deepcopy(list(task_config_data.keys()))
        companies_local = sorted({
            company
            for location_dict in task_config_data.values()
            for company in location_dict.keys()})
        tasks_local = copy.deepcopy([
            {
                **task,
                "location": location,
                "company": company
            }
            for location, location_dict in task_config_data.items()
            for company, company_tasks in location_dict.items()
            for task in company_tasks])

        self.handle(
            locations, 
            locations_local,
            "address",
            "address",
            task_config_data,
            "locations",
            add_location,
            add_local_location,
            edit_local_location,
            delete_local_location)
        self.handle(
            companies, 
            companies_local,
            "name",
            "name",
            task_config_data,
            "companies",
            add_company,
            add_local_company,
            edit_local_company,
            delete_local_company)

        self.handle(
            tasks, 
            tasks_local,
            "id",
            "id",
            task_config_data,
            "tasks",
            add_task,
            add_local_task,
            edit_local_task,
            delete_local_task)
        self.handle(
            users, 
            copy.deepcopy(users_data),
            "id",
            "id",
            users_data,
            "users",
            add_user,
            add_local_user,
            edit_local_user,
            delete_local_user)
        self.handle(
            contracts, 
            copy.deepcopy(users_data),
            "user_id",
            "id",
            users_data,
            "contracts",
            update_user,
            add_local_contract,
            edit_local_contract,
            delete_local_user)
        self.handle(
            shifts,
            copy.deepcopy(shifts_data),
            "id",
            "id",
            shifts_data,
            "shifts",
            add_shift,
            add_local_shift,
            edit_local_shift,
            delete_local_shift)
        self.handle(
            requests,
            copy.deepcopy(requests_data),
            "id",
            "id",
            requests_data,
            "requests",
            add_request,
            add_local_request,
            edit_local_request,
            delete_local_request)

        shifts_dict = {}
        for shift in shifts_data:
            company = shift.pop("company")
            user_id = shift.pop("user_id")
            path = f"Database/Fyrirtaeki/{company}/{user_id}.json"
            if path in shifts_dict.keys():
                shifts_dict[path].append(shift)
            else:
                shifts_dict[path] = [shift]
        requests_dict = {}
        for request in requests_data:
            company = request.pop("company")
            user_id = request.pop("user_id")
            path = f"Database/requests/{company}/{user_id}_requests.json"
            if path in requests_dict.keys():
                requests_dict[path].append(request)
            else:
                requests_dict[path] = []

        write_to_file(
            to_iso(users_data), 
            "Database/users.json")
        write_to_file(
            to_iso(task_config_data),
            "Database/task_config.json")
        for path, data in shifts_dict.items():
            write_to_file(
                to_iso(data),
                path)
        for path, data in requests_dict.items():
            write_to_file(
                to_iso(data),
                path)
        try:
            self.cur.execute(f"SET app.source = '{LOCATION}'")
            self.conn.commit()
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"DB error: {e}")

        #   $ load current data with _load_json or whatever
        #   $ pull all from db and store in dict or whatever
        #   for all id in db not in local - add to local (dont save yet)
        #   for all id in both - if updated > last sync: update local
        #   for all id only in local:
        #       if id in deleted_history and ts > last sync - delete local
        #       else push to db
        #   now save local

    def handle(self,
               rows,
               local_rows,
               db_identifier,
               local_identifier,
               data,
               table,
               add_func,
               add_local_func,
               edit_local_func,
               delete_local_func):
        types = [isinstance(x, dict) for x in local_rows]
        if True in types:
            local_ids = [r[local_identifier] for r in local_rows]
        else:
            local_ids = local_rows

        for row in rows:
            id = row[db_identifier]
            if id not in local_ids:
                res = add_local_func(row, data, self.cur)
                if res != None:
                    user_id, company = res
                    data[:] = [
                        {
                            **thing,
                            "company": company,
                            "user_id": user_id
                        } 
                        if thing["id"] == id
                        else thing
                        for thing in data]
                continue
            updated = row["updated_at"]
            if id in local_ids and updated > self.last_sync:
                edit_local_func(row, data, self.cur)
        for local_id, local_row in zip(local_ids, local_rows):
            if local_id not in [row[db_identifier] for row in rows]:
                deleted, ts = self.resolve_deleted(db_identifier, local_id, table)
                if deleted and ts > self.last_sync:
                    delete_local_func(local_row, data)
                else:
                    add_func(self.cur, local_row)
                    
    def resolve_deleted(self, id, table, identifier):
        self.cur.execute("SELECT deletion_timestamp FROM delete_history WHERE data->>%s = %s AND from_table = %s", [identifier, id, table])
        deleted_ts = self.cur.fetchone()
        if deleted_ts is None:
            return (False, datetime.now())
        return (True, deleted_ts[0])

def write_to_file(data, path):
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tmp_file:
        json.dump(data, tmp_file, indent=4, ensure_ascii=False)
        temp_path = tmp_file.name
    os.replace(temp_path, path)

def to_iso(data):
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
            else:
                to_iso(v)
    if isinstance(data, list):
        for i, v in enumerate(data):
            if isinstance(v, datetime):
                data[i] = v.isoformat()
            else:
                to_iso(v)
    return data

if __name__ == "__main__":
    merge = Merge()

































