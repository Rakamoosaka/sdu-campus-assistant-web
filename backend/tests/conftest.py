"""Every test gets a fresh temporary SQLite database, never a user's database."""
import os
from pathlib import Path
import tempfile
os.environ['DATABASE_URL'] = 'sqlite://'
import pytest
from sqlmodel import create_engine, SQLModel
from fastapi.testclient import TestClient
from app import main

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    test_engine = create_engine(f'sqlite:///{tmp_path / "campus.db"}', connect_args={'check_same_thread': False})
    monkeypatch.setattr(main, 'engine', test_engine)
    main.seed_database()
    yield
    test_engine.dispose()

@pytest.fixture
def api_client():
    with TestClient(main.app) as client:
        yield client
