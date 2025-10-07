from lib.watcher import JSONChangeHandler


JSONChangeHandler(users_callback, "Database")
JSONChangeHandler(tasks_callback, "Database")
JSONChangeHandler(shifts_callback, "Database")
JSONChangeHandler(requests_callback, "Database")

def users_callback(diffs):
    for diff in diffs:
        if diff["type"] == "added":

        if diff["type"] == "changed":
        if diff["type"] == "removed":


