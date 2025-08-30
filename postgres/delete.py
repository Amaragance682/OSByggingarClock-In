import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
cur = conn.cursor()

cur.execute("""
DROP TABLE IF EXISTS requests CASCADE;
DROP TABLE IF EXISTS company_user_relation CASCADE;
DROP TABLE IF EXISTS time_entries CASCADE;
DROP TABLE IF EXISTS union_contracts CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS companies CASCADE;
DROP TABLE IF EXISTS locations CASCADE;
""")

conn.commit()
cur.close()
conn.close()
