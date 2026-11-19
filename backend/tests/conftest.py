"""Every test gets a fresh temporary database, never a user's database.

By default that is a SQLite file. Set TEST_DATABASE_URL to a throwaway Postgres database to run the
same tests on Postgres; its public schema is wiped before every test.
"""
import os
from pathlib import Path
import tempfile
os.environ['DATABASE_URL'] = 'sqlite://'
import pytest
from sqlalchemy import text
from sqlmodel import create_engine, SQLModel
from fastapi.testclient import TestClient
from app import main

POSTGRES_URL = os.getenv('TEST_DATABASE_URL')


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    from app import ai_assistant
    ai_assistant._requests.clear()
    if POSTGRES_URL:
        test_engine = create_engine(POSTGRES_URL)
        with test_engine.begin() as connection:
            connection.execute(text('DROP SCHEMA public CASCADE; CREATE SCHEMA public'))
    else:
        test_engine = create_engine(f'sqlite:///{tmp_path / "campus.db"}', connect_args={'check_same_thread': False})
    monkeypatch.setattr(main, 'engine', test_engine)
    main.seed_database()
    yield
    test_engine.dispose()

@pytest.fixture
def api_client():
    with TestClient(main.app) as client:
        yield client
