"""Disposable database for browser tests. Never points at sdu_campus.db."""
import os
import tempfile
from pathlib import Path
import sys
import uvicorn
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
with tempfile.TemporaryDirectory(prefix='sdu-web-e2e-') as folder:
    os.environ['DATABASE_URL'] = f'sqlite:///{folder}/e2e.db'
    os.environ['CORS_ORIGINS'] = 'http://127.0.0.1:5174'
    uvicorn.run('app.main:app', host='127.0.0.1', port=8001)
