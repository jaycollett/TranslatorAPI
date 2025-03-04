from flask import Flask, request, jsonify, g
import sqlite3
import uuid
import os
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
DATABASE = 'translations.db'
API_KEY = os.getenv("TRANSLATION_API_KEY", "your_default_api_key")  # Use env variable for security

def get_db():
    """Connects to the database."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initializes the database with necessary tables."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sermon_guid TEXT NOT NULL UNIQUE,
                transcription TEXT NOT NULL,
                current_language TEXT NOT NULL,
                convert_to_language TEXT NOT NULL,
                region TEXT NOT NULL,
                translated_text TEXT DEFAULT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP DEFAULT NULL
            )
        ''')
        db.commit()
    logging.info("✅ Database initialized successfully.")

def purge_old_completed_jobs():
    """Deletes translation jobs that were completed more than 24 hours ago."""
    try:
        db = get_db()
        cursor = db.cursor()
        threshold_time = (datetime.utcnow() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("DELETE FROM translations WHERE status = 'completed' AND finished_at <= ?", (threshold_time,))
        db.commit()
        logging.info("🗑️ Purged completed translation jobs older than 24 hours.")
    except Exception as e:
        logging.error(f"❌ Error while purging old completed jobs: {e}")

@app.before_request
def require_api_key():
    """Middleware to enforce API Key authentication."""
    key = request.headers.get('X-API-KEY')
    if key != API_KEY:
        logging.warning("🚨 Unauthorized access attempt.")
        return jsonify({"error": "Unauthorized"}), 401

@app.teardown_appcontext
def close_connection(exception):
    """Closes database connection at the end of request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
    logging.debug("🔌 Database connection closed.")

@app.route('/purge', methods=['POST'])
def purge_jobs():
    """Manually trigger purge of completed jobs older than 24 hours."""
    try:
        purge_old_completed_jobs()
        return jsonify({"message": "Old completed jobs purged successfully."}), 200
    except Exception as e:
        logging.exception("❌ Error occurred while purging jobs.")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logging.info("🔥 Starting Translation API Server...")
    init_db()
    purge_old_completed_jobs()
    logging.info("✅ Translation API Server started successfully.")
    app.run(host='0.0.0.0', port=5090, debug=True, use_reloader=False)
