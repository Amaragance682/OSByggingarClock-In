import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    pin TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS company_user_relation (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id        UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role              TEXT CHECK(role IN ('employee','contractor','admin','manager')),
    union_contract_id UUID REFERENCES union_contracts(id),
    custom_settings   JSONB,
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE(user_id, company_id)
);

CREATE TABLE IF NOT EXISTS union_contracts (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    settings        JSONB NOT NULL,
    created_at      TIMESTAMP DEFAULT now()
)

CREATE TABLE IF NOT EXISTS time_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_user_relation_id UUID REFERENCES company_user_relation(id),
    location_id UUID REFERENCES locations(id),
    task_id UUID REFERENCES tasks(id),
    clock_in TIMESTAMP NOT NULL,
    clock_out TIMESTAMP,
    commute_minutes INT DEFAULT 0,
    lunch_minutes INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    company_id INT NOT NULL REFERENCES companies(id),
    location_id INT NOT NULL REFERENCES locations(id),
    completed BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES users(id),
    task_id INT NOT NULL REFERENCES tasks(id),
    requested_start TIMESTAMP NOT NULL,
    requested_end TIMESTAMP NOT NULL,
    reason TEXT,
    status TEXT CHECK (status IN ('pending','approved','rejected')) DEFAULT 'pending'
);
""")

conn.commit()
cur.close()
conn.close()
