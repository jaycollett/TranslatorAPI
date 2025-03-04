import sqlite3
import time
import logging
from google.cloud import translate_v2 as translate
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Database and API settings
DATABASE = 'translations.db'
SERVICE_ACCOUNT_JSON = '/etc/secrets/key.json'  # Path to Google API credentials
TRANSLATION_POLL_INTERVAL = 10  # Seconds between checks

def get_db_connection():
    """Creates a new database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def translate_text(text, source_language, target_language, region):
    """Translates text using Google Cloud Translate API with regional settings."""
    translate_client = translate.Client.from_service_account_json(SERVICE_ACCOUNT_JSON)
    
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    
    result = translate_client.translate(
        text,
        source_language=source_language,
        target_language=target_language,
        model="nmt"
    )
    
    return result.get("translatedText", "")

def process_translation_jobs():
    """Checks for pending translations and processes them."""
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Fetch pending translation requests (now including sermon_title)
            cursor.execute(
                "SELECT id, transcription, sermon_title, current_language, convert_to_language, region FROM translations WHERE status = 'pending' LIMIT 5"
            )
            jobs = cursor.fetchall()

            if not jobs:
                logging.info("⏳ No pending translations. Waiting...")
            
            for job in jobs:
                job_id = job['id']
                transcription = job['transcription']
                sermon_title = job['sermon_title']
                source_language = job['current_language']
                target_language = job['convert_to_language']
                region = job['region'] if job['region'] else "US"  # Default to US if region is not set
                
                logging.info(f"🌍 Processing translation job {job_id}: {source_language} → {target_language} (Region: {region})...")
                
                try:
                    # Translate both transcription and sermon title
                    translated_text = translate_text(transcription, source_language, target_language, region)
                    translated_sermon_title = translate_text(sermon_title, source_language, target_language, region)
                    finished_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Update database with both translated texts, status, and finished time
                    cursor.execute(
                        "UPDATE translations SET translated_text = ?, translated_sermon_title = ?, status = 'completed', finished_at = ? WHERE id = ?",
                        (translated_text, translated_sermon_title, finished_at, job_id)
                    )
                    conn.commit()
                    
                    logging.info(f"✅ Translation job {job_id} completed successfully.")
                except Exception as e:
                    logging.error(f"❌ Translation job {job_id} failed: {e}")
                    cursor.execute(
                        "UPDATE translations SET status = 'failed' WHERE id = ?",
                        (job_id,)
                    )
                    conn.commit()
            
            conn.close()
            time.sleep(TRANSLATION_POLL_INTERVAL)
        except Exception as e:
            logging.error(f"🚨 Error in translation worker: {e}")
            time.sleep(TRANSLATION_POLL_INTERVAL)

if __name__ == "__main__":
    logging.info("🔥 Starting translation worker...")
    process_translation_jobs()
