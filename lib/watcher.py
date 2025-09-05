import os
import time
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def _load_json(path, retries=3, delay=0.05):
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

        now = time.time()
        if event.src_path in self._last_modified and now - self._last_modified[event.src_path] < 0.1:
            return

        if event.src_path in self.locked_files:
            return

        self._last_modified[event.src_path] = now

        new_data = _load_json(event.src_path)
        if new_data is not None:
            common = {k: self.previous_data[k] for k in new_data.keys() if k in self.previous_data}
            if common == {}:
                for key in new_data.keys():
                    common[key] = []
            changes = self.detect_changes(common, new_data)
            success = self.callback(changes)
            self.previous_data = new_data

    def detect_changes(self, old, new, path=[]):
        if old == new:
            return []

        diffs = []

        if isinstance(new, list) and isinstance(old, list):
            for old_item in old:
                id = old_item["id"]
                same = [n for n in new if n["id"] == id]
                if len(same) > 0:
                    same = same[0]
                    diffs.extend(self.detect_changes(old_item, same, path.copy() + [id]))
                else:
                    diffs.append({
                        "type": "removed",
                        "value": old_item,
                        "path": path
                    })
            for new_item in new:
                id = new_item["id"]
                same = [o for o in old if o["id"] == id]
                if len(same) == 0:
                    diffs.append({
                        "type": "added",
                        "value": new_item,
                        "path": path
                    })
        elif isinstance(old, dict) and isinstance(new, dict):
            for old_key, old_val in old.items():
                if old_key in new:
                    diffs.extend(self.detect_changes(old_val, new[old_key], path.copy() + [old_key]))
                else:
                    diffs.append({
                        "type": "removed",
                        "value": old_val,
                        "path": path.copy() + [old_key]
                    })
            for new_key, new_val in new.items():
                if new_key not in old:
                    diffs.append({
                        "type": "added",
                        "value": new_val,
                        "path": path.copy() + [new_key]
                    })

        else:
            diffs.append({
                "type": "changed",
                "value": new,
                "path": path
            })

        return diffs
