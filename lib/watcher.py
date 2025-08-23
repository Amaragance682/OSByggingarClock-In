import os
import time
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class JSONChangeHandler(FileSystemEventHandler):
    def __init__(self, callback, path):
        self.path = path
        self.previous_data = self._load_json(self.path)
        self.callback = callback
        self._last_modified = {}

    def _load_json(self, path, retries=3, delay=0.05):
        for attempt in range(retries):
            try:
                json_files = []
                if os.path.isfile(path):
                    if path.endswith(".json"):
                        json_files.append(path)
                else:
                    for dirpath, _, filenames in os.walk(path):
                        for file in filenames:
                            if file.endswith(".json"):
                                json_files.append(os.path.join(dirpath, file))
                collective_data = {}
                for j in json_files:
                    with open(j, "r", encoding="utf-8") as f:
                        collective_data[j] = json.load(f)
                return collective_data
            except json.JSONDecodeError:
                if attempt < retries - 1:
                    time.sleep(delay)
                    continue
                raise
            except Exception:
                return None
        return None

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".json"):
            return

        now = time.time()
        if event.src_path in self._last_modified and now - self._last_modified[event.src_path] < 0.1:
            return
        self._last_modified[event.src_path] = now

        new_data = self._load_json(event.src_path)
        if new_data is not None:
            common = {k: self.previous_data[k] for k in new_data.keys() if k in self.previous_data}
            changes = self.detect_changes(common, new_data)
            success = self.callback(changes)
            if success:
                self.previous_data = new_data

    def detect_changes(self, old, new, path=""):
        if old == new:
            return []

        changes = []

        if isinstance(old, dict) and isinstance(new, dict):
            old_keys = set(old.keys())
            new_keys = set(new.keys())

            for k in new_keys - old_keys:
                changes.append({
                    "type": "added",
                    "path": f"{path + "." if path else ''}{k}",
                    "value": new[k]
                })
            for k in old_keys - new_keys:
                changes.append({
                    "type": "removed",
                    "path": f"{path + "." if path else ''}{k}",
                    "value": old[k]
                })
            for k in old_keys & new_keys:
                changes.extend(self.detect_changes(old[k], new[k], path + "." + k if path else k))

        elif isinstance(old, list) and isinstance(new, list):
            min_len = min(len(old), len(new))
            for i in range(min_len):
                changes.extend(self.detect_changes(old[i], new[i], f"{path}[{i}]"))
            if len(new) > len(old):
                for i in range(min_len, len(new)):
                    changes.append({
                        "type": "added",
                        "path": f"{path}[{i}]",
                        "value": new[i]
                    })
            elif len(old) > len(new):
                for i in range(min_len, len(old)):
                    changes.append({
                        "type": "removed",
                        "path": f"{path}[{i}]",
                        "value": old[i]
                    })

        else:
            changes.append({
                "type": "changed",
                "path": f"{path}",
                "from": old,
                "to": new
            })

        return changes
