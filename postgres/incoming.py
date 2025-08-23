import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    address TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    company_id INT NOT NULL REFERENCES companies(id),
    pin TEXT NOT NULL,
    commute_minutes INT DEFAULT 0,
    lunch_minutes INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    company_id INT NOT NULL REFERENCES companies(id),
    location_id INT NOT NULL REFERENCES locations(id),
    completed BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS requests (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    task_id INT NOT NULL REFERENCES tasks(id),
    requested_start TIMESTAMP NOT NULL,
    requested_end TIMESTAMP NOT NULL,
    reason TEXT,
    status TEXT CHECK (status IN ('pending','approved','rejected')) DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS work_logs (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    task_id INT NOT NULL REFERENCES tasks(id),
    clock_in TIMESTAMP NOT NULL,
    clock_out TIMESTAMP,
    commute_minutes INT DEFAULT 0,
    lunch_minutes INT DEFAULT 0
);
""")

conn.commit()
cur.close()
conn.close()
