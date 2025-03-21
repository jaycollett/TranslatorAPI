from flask import Flask, request, jsonify, g
import sqlite3
import uuid
import os
import logging
import threading
import time
from datetime import datetime, timedelta
from translation_worker import process_translation_jobs

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
        db.commit()
    logging.info("Database initialized successfully.")

def purge_old_completed_jobs():
    """Deletes translation jobs that were completed more than 4 hours ago."""
    try:
        db = get_db()
        cursor = db.cursor()
        threshold_time = (datetime.utcnow() - timedelta(hours=4)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("DELETE FROM translations WHERE status = 'completed' AND finished_at <= ?", (threshold_time,))
        deleted_count = cursor.rowcount
        db.commit()
        if deleted_count > 0:
            logging.info(f"Purged {deleted_count} completed translation jobs older than 4 hours.")
    except Exception as e:
        logging.error(f"Error while purging old completed jobs: {e}")

@app.before_request
def require_api_key():
    """Middleware to enforce API Key authentication."""
    key = request.headers.get('X-API-KEY')
    if key != API_KEY:
        logging.warning("Unauthorized access attempt.")
        return jsonify({"error": "Unauthorized"}), 401

@app.teardown_appcontext
def close_connection(exception):
    """Closes database connection at the end of request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/translate', methods=['POST'])
def request_translation():
    """Endpoint to submit a translation request."""
    try:
        data = request.get_json()
        sermon_guid = data.get('sermon_guid')
        sermon_title = data.get('sermon_title')  
        transcription = data.get('transcription')
        current_language = data.get('current_language')
        convert_to_language = data.get('convert_to_language')
        region = data.get('region')

        # Check if all required fields are provided
        if not all([sermon_guid, sermon_title, transcription, current_language, convert_to_language, region]):
            logging.error("Missing required fields in request.")
            return jsonify({"error": "Missing required fields"}), 400

        db = get_db()
        cursor = db.cursor()

        # Check if sermon GUID already exists
        cursor.execute('SELECT id FROM translations WHERE sermon_guid = ?', (sermon_guid,))
        existing = cursor.fetchone()
        if existing:
            logging.warning(f"Duplicate sermon GUID detected: {sermon_guid}")
            return jsonify({"error": "A translation request for this sermon already exists."}), 409

        cursor.execute('''
            INSERT INTO translations (sermon_guid, sermon_title, transcription, current_language, convert_to_language, region, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        ''', (sermon_guid, sermon_title, transcription, current_language, convert_to_language, region))
        db.commit()
        logging.info(f"Translation request submitted: {sermon_guid}")
        return jsonify({"message": "Translation request submitted successfully"}), 201

    except Exception as e:
        logging.exception(f"Error occurred while processing translation request: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/')
def index():
    """Default route serving a blank page."""
    return "", 200

@app.route('/status/<sermon_guid>', methods=['GET'])
def get_translation_status(sermon_guid):
    """Fetches the status of a translation job by sermon GUID, returning only the translated fields and timestamps."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM translations WHERE sermon_guid = ?", (sermon_guid,))
        row = cursor.fetchone()

        if row is None:
            logging.warning(f"Translation status request: Sermon GUID not found - {sermon_guid}")
            return jsonify({"error": "Translation job not found."}), 404

        translation_data = dict(row)
        logging.info(f"Translation status retrieved for Sermon GUID: {sermon_guid}")

        # Only return the desired fields
        response_data = {
            "sermon_guid": translation_data.get("sermon_guid"),
            "translated_sermon_title": translation_data.get("translated_sermon_title"),
            "translated_text": translation_data.get("translated_text"),
            "status": translation_data.get("status"),
            "created": translation_data.get("created"),
            "convert_to_language": translation_data.get("convert_to_language"),
            "finished": translation_data.get("finished_at")
        }

        return jsonify(response_data), 200

    except Exception as e:
        logging.exception(f"Error occurred while fetching translation status: {e}")
        return jsonify({"error": str(e)}), 500


def schedule_purge_task():
    """Periodically purges old completed translation jobs."""
    PURGE_INTERVAL = 15 * 60  # Run purge every 15 minutes
    
    while True:
        time.sleep(PURGE_INTERVAL)
        with app.app_context():
            try:
                purge_old_completed_jobs()
            except Exception as e:
                logging.error(f"Scheduled purge task failed: {e}")

if __name__ == "__main__":
    logging.info("Starting Translation API Server...")
    init_db()

    # Run initial purge
    with app.app_context():
        purge_old_completed_jobs()
        
    # Start translation worker thread
    logging.info("Starting translation worker thread...")
    worker_thread = threading.Thread(target=process_translation_jobs, daemon=True)
    worker_thread.start()
    logging.info("Translation worker thread started successfully.")
    
    # Start automatic purge thread
    logging.info("Starting automatic purge thread...")
    purge_thread = threading.Thread(target=schedule_purge_task, daemon=True)
    purge_thread.start()
    logging.info("Automatic purge thread started successfully.")
    
    logging.info("Translation API Server started successfully.")
    app.run(host='0.0.0.0', port=5090, debug=True, use_reloader=False)
