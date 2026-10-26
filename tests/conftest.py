import pytest

from app.catalog.db import connect
from data.seed import seed


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "t.db"
    seed(path=path)
    c = connect(path)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    from app import main
    main._hits.clear()
    yield
    main._hits.clear()
