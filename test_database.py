import pytest
import os
import sqlite3
from database import init_db, get_db, execute_with_params
import threading
import time

# Use a test database file
TEST_DB = 'test_translations.db'

@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup before each test and cleanup after."""
    # Setup: Set test database path
    os.environ['DATABASE_PATH'] = TEST_DB
    
    yield  # This is where the test runs
    
    # Teardown: Remove test database
    try:
        os.remove(TEST_DB)
    except FileNotFoundError:
        pass
    # Remove the environment variable
    os.environ.pop('DATABASE_PATH', None)

def test_init_db():
    """Test database initialization."""
    init_db()
    
    # Verify table exists
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='translations'")
    assert cursor.fetchone() is not None
    
    # Verify table schema
    cursor.execute("PRAGMA table_info(translations)")
    columns = {row[1] for row in cursor.fetchall()}
    expected_columns = {
        'id', 'sermon_guid', 'sermon_title', 'transcription',
        'current_language', 'convert_to_language', 'region',
        'translated_text', 'translated_sermon_title', 'status',
        'created_at', 'finished_at'
    }
    assert columns == expected_columns
    conn.close()

def test_execute_with_params_insert():
    """Test inserting data with parameters."""
    init_db()
    
    # Test insert
    execute_with_params(
        "INSERT INTO translations (sermon_guid, sermon_title, transcription, current_language, convert_to_language, region) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ('test-guid', 'Test Sermon', 'Test Content', 'en', 'es', 'US')
    )
    
    # Verify insert
    result = execute_with_params("SELECT * FROM translations WHERE sermon_guid = ?", ('test-guid',))
    assert len(result) == 1
    assert result[0]['sermon_guid'] == 'test-guid'
    assert result[0]['sermon_title'] == 'Test Sermon'
    assert result[0]['status'] == 'pending'

def test_execute_with_params_update():
    """Test updating data with parameters."""
    init_db()
    
    # Insert test data
    execute_with_params(
        "INSERT INTO translations (sermon_guid, sermon_title, transcription, current_language, convert_to_language, region) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ('test-guid', 'Test Sermon', 'Test Content', 'en', 'es', 'US')
    )
    
    # Test update
    execute_with_params(
        "UPDATE translations SET status = ?, translated_text = ? WHERE sermon_guid = ?",
        ('completed', 'Translated Content', 'test-guid')
    )
    
    # Verify update
    result = execute_with_params("SELECT * FROM translations WHERE sermon_guid = ?", ('test-guid',))
    assert result[0]['status'] == 'completed'
    assert result[0]['translated_text'] == 'Translated Content'

def test_execute_with_params_delete():
    """Test deleting data with parameters."""
    init_db()
    
    # Insert test data
    execute_with_params(
        "INSERT INTO translations (sermon_guid, sermon_title, transcription, current_language, convert_to_language, region) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ('test-guid', 'Test Sermon', 'Test Content', 'en', 'es', 'US')
    )
    
    # Test delete
    execute_with_params("DELETE FROM translations WHERE sermon_guid = ?", ('test-guid',))
    
    # Verify delete
    result = execute_with_params("SELECT * FROM translations WHERE sermon_guid = ?", ('test-guid',))
    assert len(result) == 0

def test_concurrent_access():
    """Test thread safety of database operations."""
    init_db()
    
    def worker(guid):
        """Worker function to insert a record."""
        execute_with_params(
            "INSERT INTO translations (sermon_guid, sermon_title, transcription, current_language, convert_to_language, region) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (f'guid-{guid}', 'Test Sermon', 'Test Content', 'en', 'es', 'US')
        )
    
    # Create and start multiple threads
    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    # Verify all records were inserted
    result = execute_with_params("SELECT COUNT(*) as count FROM translations")
    assert result[0]['count'] == 10

def test_error_handling():
    """Test error handling in database operations."""
    init_db()
    
    # Test duplicate unique key
    execute_with_params(
        "INSERT INTO translations (sermon_guid, sermon_title, transcription, current_language, convert_to_language, region) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ('test-guid', 'Test Sermon', 'Test Content', 'en', 'es', 'US')
    )
    
    # Attempt to insert duplicate sermon_guid should raise an exception
    with pytest.raises(sqlite3.IntegrityError):
        execute_with_params(
            "INSERT INTO translations (sermon_guid, sermon_title, transcription, current_language, convert_to_language, region) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ('test-guid', 'Another Sermon', 'More Content', 'en', 'fr', 'CA')
        )

def test_dict_factory():
    """Test that results are returned as dictionaries."""
    init_db()
    
    # Insert test data
    execute_with_params(
        "INSERT INTO translations (sermon_guid, sermon_title, transcription, current_language, convert_to_language, region) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ('test-guid', 'Test Sermon', 'Test Content', 'en', 'es', 'US')
    )
    
    # Query and verify result format
    result = execute_with_params("SELECT * FROM translations WHERE sermon_guid = ?", ('test-guid',))
    assert isinstance(result[0], dict)
    assert all(isinstance(key, str) for key in result[0].keys())
    assert 'sermon_guid' in result[0]
    assert 'sermon_title' in result[0]
