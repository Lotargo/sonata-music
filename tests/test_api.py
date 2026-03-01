import pytest
import os
import io
import sys

# Add src to path if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from audio_upscaler.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    # Ensure directories exist for test
    os.makedirs('library/uploads', exist_ok=True)
    os.makedirs('library/processed', exist_ok=True)
    with app.test_client() as client:
        yield client

def test_health(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    assert res.json['status'] == 'healthy'

def test_library(client):
    res = client.get('/api/library')
    assert res.status_code == 200
    assert 'uploads' in res.json
    assert 'processed' in res.json

def test_upload(client):
    data = {
        'file': (io.BytesIO(b"dummy audio content"), 'test_upload.wav')
    }
    res = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert res.status_code == 201
    assert res.json['filename'] == 'test_upload.wav'
    assert os.path.exists('library/uploads/test_upload.wav')
    # Cleanup
    if os.path.exists('library/uploads/test_upload.wav'):
        os.remove('library/uploads/test_upload.wav')

def test_upload_invalid_type(client):
    data = {
        'file': (io.BytesIO(b"dummy content"), 'test.txt')
    }
    res = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert res.status_code == 400
    assert 'error' in res.json
