import pytest
from fastapi.testclient import TestClient

from app.catalog.db import connect
from app.main import app, get_conn
from data.seed import seed


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "t.db"
    seed(path=path)
    conn = connect(path)
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()
    conn.close()


def test_products_filters(client):
    rows = client.get("/products", params={"use": "sports", "size": 9, "limit": 4}).json()["products"]
    assert 0 < len(rows) <= 4 and all(r["use_type"] == "sports" for r in rows)


def test_product_detail_and_404(client):
    p = client.get("/products/1").json()
    assert p["id"] == 1 and "sizes_in_stock" in p
    assert client.get("/products/99999").status_code == 404


def test_api_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"name": "shopper-api", "status": "running"}


def test_products_by_ids_keeps_order(client):
    ids = client.get("/products", params={"use": "casual", "limit": 3}).json()["products"]
    wanted = [r["id"] for r in reversed(ids)]
    got = client.get("/products", params={"ids": ",".join(map(str, wanted))}).json()["products"]
    assert [r["id"] for r in got] == wanted
    assert client.get("/products", params={"ids": "x"}).status_code == 400


def test_cart_checkout_order_over_http(client):
    shoe = next(p for p in client.get("/products", params={"size": 9, "limit": 1}).json()["products"])
    body = {"session_id": "http1", "user_id": "uh", "product_id": shoe["id"], "size": 9}
    assert client.post("/cart/add", json=body).json()["total"] == shoe["price"]
    assert client.post("/cart/add", json={**body, "size": 99}).status_code == 409
    order = client.post("/checkout", json={"session_id": "http1", "user_id": "uh"}).json()
    assert client.get("/orders/" + order["order_id"]).json()["total"] == shoe["price"]
    assert client.post("/checkout", json={"session_id": "http1"}).status_code == 400
    assert client.get("/cart", params={"session_id": "http1"}).json()["items"] == []
