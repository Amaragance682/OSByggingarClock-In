def add_user(cur, value):

  id              SERIAL PRIMARY KEY,
name            TEXT NOT NULL,
email           TEXT UNIQUE NOT NULL,
password_hash   TEXT NOT NULL,
created_at      TIMESTAMP DEFAULT now()
