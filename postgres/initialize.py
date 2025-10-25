import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
cur = conn.cursor()

cur.execute(f"""
CREATE TABLE IF NOT EXISTS locations (
    address TEXT NOT NULL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS companies (
    name TEXT NOT NULL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    company TEXT NOT NULL REFERENCES companies(name) ON DELETE CASCADE,
    location TEXT NOT NULL REFERENCES locations(address) ON DELETE CASCADE,
    completed BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    pin TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contracts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company           TEXT NOT NULL REFERENCES companies(name) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role              TEXT CHECK(role IN ('employee','contractor','admin','manager')) DEFAULT 'employee',
    custom_settings   JSONB,
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE(user_id, company)
);

CREATE TABLE IF NOT EXISTS shifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID REFERENCES contracts(id),
    location TEXT REFERENCES locations(address),
    task_id UUID REFERENCES tasks(id),
    clock_in TIMESTAMP NOT NULL,
    clock_out TIMESTAMP,
    extra JSONB,
    created_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    company TEXT NOT NULL REFERENCES companies(name) ON DELETE CASCADE,
    location TEXT NOT NULL REFERENCES locations(address) ON DELETE CASCADE,
    requested_start TIMESTAMP NOT NULL,
    requested_end TIMESTAMP NOT NULL,
    extra JSONB,
    reason TEXT,
    status TEXT CHECK (status IN ('pending','approved','rejected')) DEFAULT 'pending'
);

CREATE OR REPLACE FUNCTION notify_request_change()
RETURNS trigger AS $$
DECLARE
  v_source text;
BEGIN
  v_source := current_setting('app.source', true);
  IF v_source IS NULL THEN
    v_source := 'unknown';
  END IF;

  IF TG_OP = 'INSERT' THEN
    PERFORM pg_notify(
      'requests_channel',
      json_build_object(
        'action', TG_OP,
        'table', TG_TABLE_NAME,
        'new', row_to_json(NEW),
        'source', v_source
      )::text
    );
    RETURN NEW;

  ELSIF TG_OP = 'UPDATE' THEN
    PERFORM pg_notify(
      'requests_channel',
      json_build_object(
        'action', TG_OP,
        'table', TG_TABLE_NAME,
        'old', row_to_json(OLD),
        'new', row_to_json(NEW),
        'source', v_source
      )::text
    );
    RETURN NEW;

  ELSIF TG_OP = 'DELETE' THEN
    PERFORM pg_notify(
      'requests_channel',
      json_build_object(
        'action', TG_OP,
        'table', TG_TABLE_NAME,
        'old', row_to_json(OLD),
        'source', v_source
      )::text
    );
    RETURN OLD;
  END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS requests_change_trigger ON companies;
DROP TRIGGER IF EXISTS requests_change_trigger ON locations;
DROP TRIGGER IF EXISTS requests_change_trigger ON users;
DROP TRIGGER IF EXISTS requests_change_trigger ON contracts;
DROP TRIGGER IF EXISTS requests_change_trigger ON tasks;
DROP TRIGGER IF EXISTS requests_change_trigger ON shifts;
DROP TRIGGER IF EXISTS requests_change_trigger ON requests;

CREATE TRIGGER requests_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON companies
FOR EACH ROW EXECUTE FUNCTION notify_request_change();

CREATE TRIGGER requests_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON locations
FOR EACH ROW EXECUTE FUNCTION notify_request_change();

CREATE TRIGGER requests_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION notify_request_change();

CREATE TRIGGER requests_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON contracts
FOR EACH ROW EXECUTE FUNCTION notify_request_change();

CREATE TRIGGER requests_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON tasks
FOR EACH ROW EXECUTE FUNCTION notify_request_change();

CREATE TRIGGER requests_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON shifts
FOR EACH ROW EXECUTE FUNCTION notify_request_change();

CREATE TRIGGER requests_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON requests
FOR EACH ROW EXECUTE FUNCTION notify_request_change();
""")

conn.commit()
cur.close()
conn.close()
