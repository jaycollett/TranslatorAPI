import requests
import time
import uuid
import logging

# Configure logging with emojis
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_guid():
    """Generates a random GUID for the translation request."""
    return str(uuid.uuid4())

# API Configuration
API_URL = "https://translator.collett.us"
API_KEY = "e95db18b-6bd6-411e-b95c-b3699b12cad3"  # Replace with your actual API key
HEADERS = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

def submit_translation_job(sermon_guid, text, source_lang="en", target_lang="es", region="mx"):
    """Submits a translation job to the API."""
    payload = {
        "sermon_guid": sermon_guid,
        "transcription": text,
        "current_language": source_lang,
        "convert_to_language": target_lang,
        "region": region
    }
    response = requests.post(f"{API_URL}/translate", json=payload, headers=HEADERS)
    if response.status_code == 201:
        logging.info(f"✅ Translation job submitted successfully! GUID: {sermon_guid}")
    else:
        logging.error(f"❌ Failed to submit translation job: {response.json()}")
    return response

def check_translation_status(sermon_guid):
    """Checks the translation status until it's completed."""
    while True:
        time.sleep(10)
        logging.info("⏳ Checking translation status...")
        response = requests.get(f"{API_URL}/status/{sermon_guid}", headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            logging.info(f"📊 Status: {data['status']}")
            if data['status'] == 'completed':
                logging.info(f"🎉 Translation completed! Translated text:\n{data['translated_text']}")
                break
            elif data['status'] == 'failed':
                logging.error("❌ Translation failed!")
                break
        else:
            logging.error(f"❌ Failed to fetch status: {response.json()}")
            break

def main():
    """Main function to test the translation API."""
    sermon_guid = generate_guid()
    test_text = """Blessed are the poor in spirit, for theirs is the kingdom of heaven. Blessed are those who mourn, for they shall be comforted. Blessed are the meek, for they shall inherit the earth. Blessed are those who hunger and thirst for righteousness, for they shall be satisfied. Blessed are the merciful, for they shall receive mercy. Blessed are the pure in heart, for they shall see God. Blessed are the peacemakers, for they shall be called sons of God. Blessed are those who are persecuted for righteousness’ sake, for theirs is the kingdom of heaven. Blessed are you when others revile you and persecute you and utter all kinds of evil against you falsely on my account. Rejoice and be glad, for your reward is great in heaven, for so they persecuted the prophets who were before you."""
    
    logging.info("🚀 Starting translation API test...")
    submit_translation_job(sermon_guid, test_text)
    check_translation_status(sermon_guid)

if __name__ == "__main__":
    main()
