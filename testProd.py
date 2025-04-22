
import requests
import time
import uuid
import logging
import json  # For pretty-printing the raw JSON

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_guid():
    """Generates a random GUID for the translation request."""
    return str(uuid.uuid4())

# API Configuration
API_URL = "https://translator.collett.us"
API_KEY = os.getenv("TRANSLATION_API_KEY")
if not API_KEY:
    logging.warning("TRANSLATION_API_KEY environment variable is not set. API requests may fail.")
HEADERS = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

def submit_translation_job(sermon_guid, text, sermon_title, source_lang="en", target_lang="es", region="mx"):
    """Submits a translation job to the API."""
    payload = {
        "sermon_guid": sermon_guid,
        "transcription": text,
        "sermon_title": sermon_title,
        "current_language": source_lang,
        "convert_to_language": target_lang,
        "region": region
    }
    response = requests.post(f"{API_URL}/translate", json=payload, headers=HEADERS)
    if response.status_code == 201:
        logging.info(f"Translation job submitted successfully. GUID: {sermon_guid}")
    else:
        logging.error(f"Failed to submit translation job: {response.json()}")
    return response

def check_translation_status(sermon_guid):
    """Checks the translation status until it's completed."""
    while True:
        time.sleep(10)
        logging.info("Checking translation status...")
        response = requests.get(f"{API_URL}/status/{sermon_guid}", headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Status: {data['status']}")
            if data['status'] == 'completed':
                logging.info("Translation completed.")
                logging.info(f"Translated text:\n{data['translated_text']}")
                sermon_title_translated = data.get("translated_sermon_title")
                if sermon_title_translated:
                    logging.info(f"Translated sermon title:\n{sermon_title_translated}")
                else:
                    logging.warning("Translated sermon title not found in the response.")
                break
            elif data['status'] == 'failed':
                logging.error("Translation failed.")
                break
        else:
            try:
                error_data = response.json()
            except Exception:
                error_data = response.text
            logging.error(f"Failed to fetch status: {error_data}")
            break

def main():
    """Main function to test the translation API."""
    sermon_guid = generate_guid()
    sermon_title = "Sermonette 3/22: Matthew 20:17-28"
    test_text = """This is a test passage with approximately 500 words. It contains a variety of sentence structures"""
    
    logging.info("Starting translation API test...")
    submit_translation_job(sermon_guid, test_text, sermon_title)
    check_translation_status(sermon_guid)

if __name__ == "__main__":
    main()