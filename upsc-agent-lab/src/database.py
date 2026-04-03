import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """
    Returns a live psycopg2 connection using DATABASE_URL from .env
    Every other module imports and calls this single function.
    """
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        return conn
    except Exception as e:
        print(f"❌ DB Connection Failed: {e}")
        raise
