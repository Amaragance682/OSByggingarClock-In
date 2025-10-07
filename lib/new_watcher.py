def detect_changes(old, new):
    diffs = []

    if isinstance(old, list) and isinstance(new, list):
        for old_item in old:
            old_id = old_item["id"]
            same = [n for n in new if n["id"] == old_id]
            if len(same) > 0:
                same = same[0]
                if is_different(old_item, same):
                    diffs.append({
                        "type": "changed",
                        "value": same
                    })
            else:
                diffs.append({
                    "type": "removed",
                    "value": old_item
                })
        for new_item in new:
            id = new_item["id"]
            same = [o for o in old if o["id"] == id]
            if len(same) == 0:
                diffs.append({
                    "type": "added",
                    "value": new_item
                })

    if isinstance(old, dict) and isinstance(new, dict):
        diffs.extend(deep_diff(old, new))

    return diffs

def deep_diff(old, new):
    diffs = []

    # Removed locations
    for location in old.keys() - new.keys():
        diffs.append({
            "type": "removed",
            "source": "location",
            "value": location
        })

    # Added locations
    for location in new.keys() - old.keys():
        diffs.append({
            "type": "added",
            "source": "location",
            "value": location
        })

    # Locations in both
    for location in old.keys() & new.keys():
        old_companies = old[location]
        new_companies = new[location]

        # Removed companies
        for company in old_companies.keys() - new_companies.keys():
            diffs.append({
                "type": "removed",
                "source": "company",
                "value": company,
                "location": location
            })

        # Added companies
        for company in new_companies.keys() - old_companies.keys():
            diffs.append({
                "type": "added",
                "source": "company",
                "value": company,
                "location": location
            })

        # Companies in both
        for company in old_companies.keys() & new_companies.keys():
            old_tasks = old_companies[company]
            new_tasks = new_companies[company]

            # Compare tasks one by one (index-based here)
            max_len = max(len(old_tasks), len(new_tasks))
            for i in range(max_len):
                if i >= len(old_tasks):
                    diffs.append({
                        "type": "added",
                        "source": "task",
                        "value": new_tasks[i],
                        "location": location,
                        "company": company
                    })
                elif i >= len(new_tasks):
                    diffs.append({
                        "type": "removed",
                        "source": "task",
                        "value": old_tasks[i],
                        "location": location,
                        "company": company
                    })
                elif old_tasks[i] != new_tasks[i]:
                    diffs.append({
                        "type": "changed",
                        "source": "task",
                        "value": new_tasks[i],
                        "location": location,
                        "company": company
                    })

    return diffs

def diff_immediate(old, new):
    diffs = []
    for o in old:
        if o not in new:
            diffs.append({
                "type": "removed",
                "value": o
            })
    for n in new:
        if n not in old:
            diffs.append({
                "type": "added",
                "value": n
            })
    return diffs

def is_different(old, new):
    for key, val in old.items():
        if key not in new.keys() or new[key] != val:
            return True
    for key, val in new.items():
        if key not in old.keys() or old[key] != val:
            return True
    return False
