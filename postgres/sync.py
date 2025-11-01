import json
import os
from pathlib import Path
import time
from dotenv import load_dotenv
import psycopg2
from postgres.incoming import Incoming
from postgres.merge import Merge
from postgres.outgoing import Outgoing
from lib.watcher import _load_json

merge = Merge()
outgoing = Outgoing()
incoming = Incoming(outgoing)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting…")
