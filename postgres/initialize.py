import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    completed BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    pin TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS union_contracts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    settings        JSONB NOT NULL,
    created_at      TIMESTAMP DEFAULT now()
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

CREATE TABLE IF NOT EXISTS time_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_user_relation_id UUID REFERENCES company_user_relation(id),
    location_id UUID REFERENCES locations(id),
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
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    requested_start TIMESTAMP NOT NULL,
    requested_end TIMESTAMP NOT NULL,
    extra JSONB,
    reason TEXT,
    status TEXT CHECK (status IN ('pending','approved','rejected')) DEFAULT 'pending'
);

CREATE OR REPLACE FUNCTION notify_request_change()
RETURNS trigger AS $$
BEGIN
  IF current_setting('app.source', true) = 'file_sync' THEN
    RETURN NEW;
  END IF;

  IF TG_OP = 'INSERT' THEN
    PERFORM pg_notify(
      'requests_channel',
      json_build_object(
        'action', TG_OP,
        'table', TG_TABLE_NAME,
        'id', NEW.id,
        'new', row_to_json(NEW)
      )::text
    );
    RETURN NEW;

  ELSIF TG_OP = 'UPDATE' THEN
    PERFORM pg_notify(
      'requests_channel',
      json_build_object(
        'action', TG_OP,
        'table', TG_TABLE_NAME,
        'id', NEW.id,
        'old', row_to_json(OLD),
        'new', row_to_json(NEW)
      )::text
    );
    RETURN NEW;

  ELSIF TG_OP = 'DELETE' THEN
    PERFORM pg_notify(
      'requests_channel',
      json_build_object(
        'action', TG_OP,
        'table', TG_TABLE_NAME,
        'id', OLD.id,
        'old', row_to_json(OLD)
      )::text
    );
    RETURN OLD;
  END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS requests_change_trigger ON companies;
DROP TRIGGER IF EXISTS requests_change_trigger ON locations;
DROP TRIGGER IF EXISTS requests_change_trigger ON users;
DROP TRIGGER IF EXISTS requests_change_trigger ON company_user_relation;
DROP TRIGGER IF EXISTS requests_change_trigger ON tasks;
DROP TRIGGER IF EXISTS requests_change_trigger ON time_entries;
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
AFTER INSERT OR UPDATE OR DELETE ON company_user_relation
FOR EACH ROW EXECUTE FUNCTION notify_request_change();

CREATE TRIGGER requests_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON tasks
FOR EACH ROW EXECUTE FUNCTION notify_request_change();

CREATE TRIGGER requests_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON time_entries
FOR EACH ROW EXECUTE FUNCTION notify_request_change();

CREATE TRIGGER requests_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON requests
FOR EACH ROW EXECUTE FUNCTION notify_request_change();
""")

conn.commit()
cur.close()
conn.close()
