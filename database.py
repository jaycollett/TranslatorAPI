import sqlite3
import os
import logging
from threading import Lock

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Database configuration
def get_db_path():
    """Get the database path from environment or default."""
    return os.getenv('DATABASE_PATH', 'translations.db')

# Thread-safe database operations
db_lock = Lock()

def dict_factory(cursor, row):
    """Convert database row to dictionary."""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

def get_db():
    """Get a database connection with row factory set to return dictionaries."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = dict_factory
    return conn

def init_db():
    """Initialize the database with required tables."""
    try:
        with db_lock:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sermon_guid TEXT NOT NULL UNIQUE,
                    sermon_title TEXT NOT NULL,
                    transcription TEXT NOT NULL,
                    current_language TEXT NOT NULL,
                    convert_to_language TEXT NOT NULL,
                    region TEXT NOT NULL,
                    translated_text TEXT DEFAULT NULL,
                    translated_sermon_title TEXT DEFAULT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP DEFAULT NULL
                )
            ''')
            conn.commit()
            conn.close()
            logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        raise

def execute_with_params(query, params=None):
    """Execute a query with parameters in a thread-safe way."""
    with db_lock:
        conn = get_db()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            result = cursor.fetchall()
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
