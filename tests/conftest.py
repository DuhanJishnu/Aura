from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app, set_service
from stylist_agent.db import AuraDatabase, set_db
from stylist_agent.memory import PreferenceStore
from stylist_agent.offline import FakeSearchBackend, OfflineStylistService
from stylist_agent.tools import set_search_backend, set_store


@pytest.fixture()
def store(tmp_path):
    db = AuraDatabase(tmp_path / "aura.db")
    set_db(db)
    st = PreferenceStore(base_dir=tmp_path / "profiles", persist=True, db=db)
    set_store(st)
    yield st
    set_db(None)
    db.close()


@pytest.fixture()
def offline_service(store):
    svc = OfflineStylistService(store=store)
    set_search_backend(FakeSearchBackend())
    set_service(svc)
    yield svc
    set_service(None)
    set_search_backend(None)


@pytest.fixture()
def client(offline_service):
    with TestClient(app) as c:
        yield c
