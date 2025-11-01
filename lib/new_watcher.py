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

    combined_locations = old.copy()
    combined_locations.update(new)
    for location in combined_locations.keys():
        if location not in old:
            diffs.append({
                "type": "added",
                "source": "location",
                "value": location
            })
            old_companies = {}
            new_companies = new[location]
        elif location not in new:
            diffs.append({
                "type": "removed",
                "source": "location",
                "value": location
            })
            old_companies = old[location]
            new_companies = {}
        else:
            old_companies = old[location]
            new_companies = new[location]

        combined_companies = old_companies.copy()
        combined_companies.update(new_companies)
        for company in combined_companies.keys():
            if company not in old_companies:
                diffs.append({
                    "type": "added",
                    "source": "company",
                    "value": company,
                    "location": location
                })
                old_tasks = {}
                new_tasks = new_companies[company]
            elif company not in new_companies:
                # accounting for companies existing in
                # different places in data, only remove if
                # no other instances exist
                if company not in [e for w in new.keys() for e in new[w]]:
                    diffs.append({
                        "type": "removed",
                        "source": "company",
                        "value": company,
                        "location": location
                    })
                old_tasks = old_companies[company]
                new_tasks = {}
            else:
                old_tasks = old_companies[company]
                new_tasks = new_companies[company]

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

    diffs.sort(key=lambda diff: diff["source"])
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

if __name__ == "__main__":
    test = {
        "Eyravegur 28-30, Selfoss": {
            "A1 málun1": [
                {
                    "id": "f35f8804-c449-4e35-b9ac-005b3f9ab12f",
                    "name": "test",
                    "completed": False
                },
                {
                    "id": "512db8f3-f487-4c88-8983-114f0188c775",
                    "name": "test2",
                    "completed": False
                },
                {
                    "id": "97db991a-2166-4b2a-893a-60a9ae4858a4",
                    "name": "task3",
                    "completed": False
                }
            ],
            "TestComapyn": []
        },
        "whatthefuckingshit3": {
            "gamer": [
                {
                    "id": "1cd69d50-d8d2-4c06-9929-6e9601fe3579",
                    "name": "gamer",
                    "completed": False
                }
            ],
            "TestComapyn": []
        },
        "test": {
            "TestComapyn": []
        },
        "Kyotogamering": {
            "gamer": [],
            "A1 málun1": [],
            "company1": [],
            "A1 málun": [
                {
                    "id": "ffa1024a-53f6-4638-a4a2-44ee15427bca",
                    "name": "kyototask1",
                    "completed": False
                },
                {
                    "id": "faa1024a-53f6-4638-a4a2-44ee15427bca",
                    "name": "kyototask3",
                    "completed": False
                },
                {
                    "id": "aaa1024a-53f6-4638-a4a2-44ee15427bca",
                    "name": "kyototask4",
                    "completed": False
                }
            ],
            "test2": [],
            "TestComapyn": []
        }
    }

    test2 = {
        "whatthefuckingshit3": {
            "gamer": [
                {
                    "id": "1cd69d50-d8d2-4c06-9929-6e9601fe3579",
                    "name": "gamer",
                    "completed": False
                }
            ],
            "TestComapyn": []
        },
        "test": {
            "TestComapyn": []
        },
        "Kyotogamering": {
            "gamer": [],
            "A1 málun1": [],
            "company1": [],
            "A1 málun": [
                {
                    "id": "ffa1024a-53f6-4638-a4a2-44ee15427bca",
                    "name": "kyototask1",
                    "completed": False
                },
                {
                    "id": "faa1024a-53f6-4638-a4a2-44ee15427bca",
                    "name": "kyototask3",
                    "completed": False
                },
                {
                    "id": "aaa1024a-53f6-4638-a4a2-44ee15427bca",
                    "name": "kyototask4",
                    "completed": False
                }
            ],
            "test2": [],
            "TestComapyn": []
        },
        "gamering": {
            "newcompanjkrle": [
                {
                    "id": "gamerid",
                    "name": "sigma",
                    "completed": True
                }
            ]
        }
    }

    result = detect_changes(test, test2)
    import json
    print(json.dumps(result, sort_keys=True, indent=4))
