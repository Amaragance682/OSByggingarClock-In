import os
import time
import json
from lib.lib import update_last_sync
from lib.new_watcher import detect_changes
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path

def _load_json(path, retries=3, delay=0.05):
    path = Path(path) 
    for attempt in range(retries):
        try:
            json_files = []

            if path.is_file() and path.suffix == ".json":
                json_files.append(path)
            else:
                for p in path.rglob("*.json"):
                    json_files.append(p)

            collective_data = {}
            for j in json_files:
                with open(j, "r", encoding="utf-8") as f:
                    normalized_key = j.as_posix()
                    collective_data[normalized_key] = json.load(f)

            return collective_data

        except json.JSONDecodeError:
            if attempt < retries - 1:
                time.sleep(delay)
                continue
            raise
        except Exception:
            return None
    return None

class JSONChangeHandler(FileSystemEventHandler):
    def __init__(self, callback, path):
        self.path = path
        self.previous_data = _load_json(self.path)
        self.callback = callback
        self._last_modified = {}
        self.locked_files = []

    def lock(self, path):
        self.locked_files.append(path)
        print(path, "locked")
    def unlock(self, path, data):
        self.locked_files.remove(path)
        if self.previous_data:
            self.previous_data[path] = data
        print(path, "unlocked")

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".json"):
            return
        if self.path not in event.src_path:
            return

        now = time.time()
        if event.src_path in self._last_modified and now - self._last_modified[event.src_path] < 0.1:
            return

        if event.src_path in self.locked_files:
            return

        self._last_modified[event.src_path] = now
        update_last_sync()

        new_data = _load_json(event.src_path)
        if new_data is not None:
            common = {k: self.previous_data[k] for k in new_data.keys() if k in self.previous_data}
            if common == {}:
                for key in new_data.keys():
                    common[key] = []
            changes = detect_changes(common.get(event.src_path), new_data.get(event.src_path))
            for a in changes:
                a['path'] = event.src_path
            self.callback(changes)
            self.previous_data = new_data
