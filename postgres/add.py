import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from lib.watcher import _load_json

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
cur = conn.cursor()

collective_data = _load_json("Database")

empty_data = {k : {} if isinstance(v, dict) else [] if isinstance(v, list) else v for k,v in collective_data.items()}


if collective_data is not None:
    users = collective_data["Database/users.json"]
    task_config = collective_data["Database/task_config.json"]
    shifts = {k.replace("Database/Fyrirtaeki/", ""): v for k,v in collective_data.items() if "Database/Fyrirtaeki" in k}
    requests = {k.replace("Database/requests/", ""): v for k,v in collective_data.items() if "Database/requests" in k}

    #print(users)
    #print(task_config)
    #print(shifts)
    #print(requests)

    # TASK_CONFIG
    unique_companies = []
    for location, companies in task_config.items():
        cur.execute("INSERT INTO locations (address) VALUES (%s)", [location])
        for company, tasks in companies.items():
            if company not in unique_companies:
                cur.execute("INSERT INTO companies (name) VALUES (%s)", [company])
                unique_companies.append(company)

            for task in tasks:
                cur.execute("INSERT INTO tasks (name, company, location, completed) VALUES (%s, %s, %s, %s)",
                            [task["name"], company, location, task["completed"]])

    # USERS
    for user in users:
        cur.execute("INSERT INTO users (id, name, pin) VALUES (%s, %s, %s)",
                    [user["id"], user["name"], user["pin"]])

        settings = {k: user[k] for k in ("commute_minutes", "lunch_minutes") if k in user}
        cur.execute("INSERT INTO contracts (company, user_id, role, custom_settings) VALUES (%s, %s, %s, %s)",
                    [user["company"], user["id"], 'employee', psycopg2.extras.Json(settings)])

    # SHIFTS / TIME_ENTRIES
    for path, user_shifts in shifts.items():
        for shift in user_shifts:
            no_ext = os.path.splitext(path)[0]
            company, user_id = no_ext.split("/", 1)

            cur.execute("SELECT id FROM tasks WHERE name=%s AND company=%s AND location=%s",
                        [shift["task"], company, shift['location']])
            task_id = cur.fetchone()[0]
            cur.execute("SELECT id FROM contracts WHERE user_id=%s AND company=%s",
                        [user_id, company])
            contract_id = cur.fetchone()[0]

            extra = {k: shift[k] for k in shift if k not in ("id", "task", "location", "clock_in", "clock_out")}

            if "clock_out" in shift:
                cur.execute("""
                            INSERT INTO shifts 
                            (id, contract_id, location, task_id, clock_in, clock_out, extra)
                            VALUES 
                            (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            [shift["id"],
                             contract_id,
                             shift["location"],
                             task_id,
                             shift["clock_in"],
                             shift["clock_out"],
                             psycopg2.extras.Json(extra)])
            else:
                cur.execute("""
                            INSERT INTO shifts 
                            (id, contract_id, location, task_id, clock_in, extra)
                            VALUES 
                            (%s, %s, %s, %s, %s, %s)
                            """,
                            [shift["id"],
                             contract_id,
                             shift["location"],
                             task_id,
                             shift["clock_in"],
                             psycopg2.extras.Json(extra)])

    # REQUESTS
    for path, user_requests in requests.items():
        for request in user_requests:
            no_ext = os.path.splitext(path)[0]
            company, user_id = no_ext.split("/", 1)
            user_id = user_id.split("_")[0]

            location = request["location"]
            cur.execute("SELECT id FROM tasks WHERE name=%s AND company=%s AND location=%s",
                        [request["task"], company, location])
            task_id = cur.fetchone()[0]

            extra = {k: request[k] for k in ("commute_minutes", "lunch_minutes") if k in request}

            cur.execute("""
                        INSERT INTO requests
                        (id, user_id, task_id, company, location, requested_start, requested_end, extra, reason, status)
                        VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        [request["id"],
                         user_id,
                         task_id,
                         company,
                         location,
                         request["requested_start"],
                         request["requested_end"],
                         psycopg2.extras.Json(extra),
                         request["reason"],
                         request["status"]])


conn.commit()
cur.close()
conn.close()
