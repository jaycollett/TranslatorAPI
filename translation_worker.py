import time
import logging
import os
from google.cloud import translate
import json
from datetime import datetime
from database import execute_with_params

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# API settings
SERVICE_ACCOUNT_JSON = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '/etc/secrets/key.json')  # Path to Google API credentials
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')  # Optionally set this in your environment
LOCATION = os.getenv('GOOGLE_TRANSLATE_LOCATION', 'global')  # Default location is 'global'
TRANSLATION_POLL_INTERVAL = 30  # Seconds between checks

def get_project_id():
    if PROJECT_ID:
        return PROJECT_ID
    # Try to get project_id from service account file
    try:
        with open(SERVICE_ACCOUNT_JSON, 'r') as f:
            info = json.load(f)
            return info.get('project_id')
    except Exception as e:
        logging.error(f"Could not determine project_id: {e}")
        raise

def translate_text(text, source_language, target_language, region):
    """Translates text using Google Cloud Translate v3 API."""
    MAX_CHARS = 30000  # Leave some buffer below the 30,720 limit
    
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    
    # Initialize client and project info once
    client = translate.TranslationServiceClient()
    project_id = get_project_id()
    parent = f"projects/{project_id}/locations/{LOCATION}"
    
    # If text is within limit, translate directly
    if len(text) <= MAX_CHARS:
        response = client.translate_text(
            request={
                "parent": parent,
                "contents": [text],
                "mime_type": "text/plain",
                "source_language_code": source_language,
                "target_language_code": target_language,
            }
        )
        return response.translations[0].translated_text if response.translations else ""
    
    # Split text into chunks for large texts
    chunks = []
    start = 0
    while start < len(text):
        end = start + MAX_CHARS
        if end >= len(text):
            chunks.append(text[start:])
            break
        
        # Try to break at sentence boundary to preserve context
        break_point = text.rfind('.', start, end)
        if break_point == -1 or break_point <= start:
            break_point = text.rfind(' ', start, end)
        if break_point == -1 or break_point <= start:
            break_point = end
            
        chunks.append(text[start:break_point])
        start = break_point + 1 if break_point < len(text) else break_point
    
    # Translate each chunk
    translated_chunks = []
    for chunk in chunks:
        # Skip empty chunks
        if not chunk.strip():
            continue
            
        response = client.translate_text(
            request={
                "parent": parent,
                "contents": [chunk],
                "mime_type": "text/plain",
                "source_language_code": source_language,
                "target_language_code": target_language,
            }
        )
        translated_chunks.append(response.translations[0].translated_text if response.translations else "")
    
    return "".join(translated_chunks)

def process_translation_jobs():
    """Checks for pending translations and processes them."""
    while True:
        try:
            # Fetch pending translation requests
            jobs = execute_with_params(
                "SELECT id, transcription, sermon_title, current_language, convert_to_language, region "
                "FROM translations WHERE status = 'pending' LIMIT 5"
            )

            if not jobs:
                logging.info("No pending translations. Waiting...")
            else:
                for job in jobs:
                    job_id = job['id']
                    transcription = job['transcription']
                    sermon_title = job['sermon_title']
                    source_language = job['current_language']
                    target_language = job['convert_to_language']
                    region = job['region'] if job['region'] else "US"  # Default to US if region is not set
                    
                    logging.info(f"Processing translation job {job_id}: {source_language} → {target_language} (Region: {region})...")
                    
                    try:
                        # Translate both transcription and sermon title
                        translated_text = translate_text(transcription, source_language, target_language, region)
                        translated_sermon_title = translate_text(sermon_title, source_language, target_language, region)
                        finished_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Update database with both translated texts, status, and finished time
                        execute_with_params(
                            "UPDATE translations "
                            "SET translated_text = ?, translated_sermon_title = ?, status = 'completed', finished_at = ? "
                            "WHERE id = ?",
                            (translated_text, translated_sermon_title, finished_at, job_id)
                        )
                        logging.info(f"Translation job {job_id} completed successfully.")
                    except Exception as e:
                        logging.error(f"Translation job {job_id} failed: {e}")
                        execute_with_params(
                            "UPDATE translations SET status = 'failed' WHERE id = ?",
                            (job_id,)
                        )
            time.sleep(TRANSLATION_POLL_INTERVAL)
        except Exception as e:
            logging.error(f"Error in translation worker: {e}")
            time.sleep(TRANSLATION_POLL_INTERVAL)

if __name__ == "__main__":
    logging.info("Starting translation worker...")
    process_translation_jobs()
