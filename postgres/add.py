import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from lib.watcher import _load_json

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
cur = conn.cursor()

collective_data = _load_json("Database")
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
    unique_companies = {}
    for location, companies in task_config.items():
        cur.execute("INSERT INTO locations (address) VALUES (%s) RETURNING id", [location])
        location_id = cur.fetchone()[0]
        for company, tasks in companies.items():
            if company not in unique_companies:
                cur.execute("INSERT INTO companies (name) VALUES (%s) RETURNING id", [company])
                company_id = cur.fetchone()[0]
                unique_companies[company] = company_id
            else:
                company_id = unique_companies[company]

            for task in tasks:
                cur.execute("INSERT INTO tasks (name, company_id, location_id, completed) VALUES (%s, %s, %s, %s)",
                            [task["name"], company_id, location_id, task["completed"]])

    # USERS
    for user in users:
        cur.execute("INSERT INTO users (id, name, pin) VALUES (%s, %s, %s)",
                    [user["id"], user["name"], user["pin"]])

        settings = {k: user[k] for k in ("commute_minutes", "lunch_minutes") if k in user}
        cur.execute("INSERT INTO company_user_relation (company_id, user_id, role, custom_settings) VALUES (%s, %s, %s, %s)",
                    [unique_companies[user["company"]], user["id"], 'employee', psycopg2.extras.Json(settings)])

    # SHIFTS / TIME_ENTRIES
    for path, user_shifts in shifts.items():
        for shift in user_shifts:
            no_ext = os.path.splitext(path)[0]
            company, user_id = no_ext.split("/", 1)

            
            cur.execute("SELECT id FROM locations WHERE address=%s", [shift["location"]])
            location_id = cur.fetchone()[0]
            cur.execute("SELECT id FROM companies WHERE name=%s", [company])
            company_id = cur.fetchone()[0]
            cur.execute("SELECT id FROM tasks WHERE name=%s AND company_id=%s AND location_id=%s",
                        [shift["task"], company_id, location_id])
            task_id = cur.fetchone()[0]
            cur.execute("SELECT id FROM company_user_relation WHERE user_id=%s AND company_id=%s",
                        [user_id, company_id])
            company_user_relation_id = cur.fetchone()[0]

            extra = {k: shift[k] for k in shift if k not in ("id", "task", "location", "clock_in", "clock_out")}

            if "clock_out" in shift:
                cur.execute("""
                            INSERT INTO time_entries 
                            (id, company_user_relation_id, location_id, task_id, clock_in, clock_out, extra)
                            VALUES 
                            (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            [shift["id"],
                             company_user_relation_id,
                             location_id,
                             task_id,
                             shift["clock_in"],
                             shift["clock_out"],
                             psycopg2.extras.Json(extra)])
            else:
                cur.execute("""
                            INSERT INTO time_entries 
                            (id, company_user_relation_id, location_id, task_id, clock_in, extra)
                            VALUES 
                            (%s, %s, %s, %s, %s, %s)
                            """,
                            [shift["id"],
                             company_user_relation_id,
                             location_id,
                             task_id,
                             shift["clock_in"],
                             psycopg2.extras.Json(extra)])

    # REQUESTS
    for path, user_requests in requests.items():
        for request in user_requests:
            no_ext = os.path.splitext(path)[0]
            company, user_id = no_ext.split("/", 1)
            user_id = user_id.split("_")[0]

            cur.execute("SELECT id FROM locations WHERE address=%s", [request["location"]])
            location_id = cur.fetchone()[0]
            cur.execute("SELECT id FROM companies WHERE name=%s", [company])
            company_id = cur.fetchone()[0]
            cur.execute("SELECT id FROM tasks WHERE name=%s AND company_id=%s AND location_id=%s",
                        [request["task"], company_id, location_id])
            task_id = cur.fetchone()[0]

            extra = {k: request[k] for k in ("commute_minutes", "lunch_minutes") if k in request}

            cur.execute("""
                        INSERT INTO requests
                        (id, user_id, task_id, company_id, location_id, requested_start, requested_end, extra, reason, status)
                        VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        [request["id"],
                         user_id,
                         task_id,
                         company_id,
                         location_id,
                         request["requested_start"],
                         request["requested_end"],
                         psycopg2.extras.Json(extra),
                         request["reason"],
                         request["status"]])


conn.commit()
cur.close()
conn.close()
