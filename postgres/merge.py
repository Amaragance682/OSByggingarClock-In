import json
import os
from pathlib import Path
from lib.watcher import _load_json
from dotenv import load_dotenv
import psycopg2


class Merge():
    def __init__(self):
        load_dotenv()

        self.conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')

        local_data = _load_json(Path("Database/"))
        print(json.dumps(local_data, sort_keys=True, indent=4))

        # first pull from db:
        #   load current data with _load_json or whatever
        #   pull all from db and store in dict or whatever
        #   for all id in db not in local - add to local (dont save yet)
        #   for all id in both - if updated > last sync: update local
        # push from local:
        #   for all id only in local:
        #       if id in deleted_history and ts > last sync - delete local
        #       else push to db
        #   now save local

if __name__ == "__main__":
    merge = Merge()
