import pytest
from fastapi.testclient import TestClient
from aider_api import app

client = TestClient(app)

def test_run_aider_endpoint():
    response = client.post(
        "/run-aider",
        json={
            "message": "add a docstring to this function",
            "files": {
                "test.py": "def hello():\n    print('Hello, World!')"
            }
        }
    )
    assert response.status_code == 200

def test_invalid_request():
    response = client.post(
        "/run-aider",
        json={
            "message": "add a docstring to this function",
            "files": {}  # Empty files dictionary should fail
        }
    )
    assert response.status_code == 422

def test_dry_run():
    response = client.post(
        "/run-aider",
        json={
            "message": "add a docstring to this function",
            "files": {
                "test.py": "def hello():\n    print('Hello, World!')"
            },
            "dry_run": True
        }
    )
    assert response.status_code == 200