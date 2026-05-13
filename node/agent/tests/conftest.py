import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ['AGENT_TOKEN'] = 'test-token'
os.environ['WG_CONFIG'] = str(Path(tempfile.mkdtemp()) / 'awg0.conf')

from agent import app


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_headers():
    return {'Authorization': 'Bearer test-token'}


@pytest.fixture(autouse=True)
def _clean_config():
    """Ensure a clean config file for each test."""
    cfg = Path(os.environ['WG_CONFIG'])
    cfg.write_text('')
    yield
    if cfg.exists():
        cfg.unlink()
    lock = cfg.with_suffix('.lock')
    if lock.exists():
        lock.unlink()
