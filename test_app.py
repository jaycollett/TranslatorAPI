import os
import pytest
import json
from app import app, init_db
from database import execute_with_params

API_KEY = os.getenv("TRANSLATION_API_KEY", "your_default_api_key")
TEST_DB = 'test_translations_api.db'

@pytest.fixture(autouse=True)
def setup_teardown():
    os.environ['DATABASE_PATH'] = TEST_DB
    init_db()
    yield
    try:
        os.remove(TEST_DB)
    except FileNotFoundError:
        pass
    os.environ.pop('DATABASE_PATH', None)

def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def auth_headers():
    return {"X-API-KEY": API_KEY}

def test_translate_missing_fields():
    with app.test_client() as client:
        resp = client.post('/translate', json={}, headers=auth_headers())
        assert resp.status_code == 400
        assert "Missing required fields" in resp.get_data(as_text=True)

def test_translate_success_and_duplicate():
    with app.test_client() as client:
        data = {
            "sermon_guid": "guid-123",
            "sermon_title": "Test Title",
            "transcription": "Test transcription",
            "current_language": "en",
            "convert_to_language": "es",
            "region": "US"
        }
        # Successful request
        resp = client.post('/translate', json=data, headers=auth_headers())
        assert resp.status_code == 201
        assert "successfully" in resp.get_data(as_text=True)
        # Duplicate request
        resp2 = client.post('/translate', json=data, headers=auth_headers())
        assert resp2.status_code == 409
        assert "already exists" in resp2.get_data(as_text=True)

def test_translate_unauthorized():
    with app.test_client() as client:
        data = {
            "sermon_guid": "guid-unauth",
            "sermon_title": "Test Title",
            "transcription": "Test transcription",
            "current_language": "en",
            "convert_to_language": "es",
            "region": "US"
        }
        resp = client.post('/translate', json=data)  # No API key
        assert resp.status_code == 401
        assert "Unauthorized" in resp.get_data(as_text=True)

def test_status_not_found():
    with app.test_client() as client:
        resp = client.get('/status/nonexistent-guid', headers=auth_headers())
        assert resp.status_code == 404
        assert "not found" in resp.get_data(as_text=True)

def test_status_success():
    # Insert a translation job manually
    execute_with_params(
        """
        INSERT INTO translations (sermon_guid, sermon_title, transcription, current_language, convert_to_language, region, status, translated_sermon_title, translated_text, finished_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("guid-status", "Title", "Transcript", "en", "es", "US", "completed", "Titulo", "Texto traducido", "2024-01-01 00:00:00")
    )
    with app.test_client() as client:
        resp = client.get('/status/guid-status', headers=auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["sermon_guid"] == "guid-status"
        assert data["translated_sermon_title"] == "Titulo"
        assert data["translated_text"] == "Texto traducido"
        assert data["status"] == "completed"
        assert data["finished"] == "2024-01-01 00:00:00"
