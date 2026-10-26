import pytest

from app.catalog.db import connect
from app.catalog.search import get_shoe, search_shoes
from data.seed import seed


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "t.db"
    seed(path=path)
    c = connect(path)
    yield c
    c.close()


def test_use_filter(conn):
    rows = search_shoes(conn, use="sports", limit=20)
    assert rows and all(r["use_type"] == "sports" for r in rows)


def test_size_requires_stock(conn):
    for r in search_shoes(conn, size=9, limit=20):
        assert 9.0 in get_shoe(conn, r["id"])["sizes_in_stock"]


def test_combined_filters_and_ranking(conn):
    rows = search_shoes(conn, use="sports", size=9, max_price=5000, limit=10)
    assert rows
    assert all(r["use_type"] == "sports" and r["price"] <= 5000 for r in rows)
    ratings = [r["rating"] for r in rows]
    assert ratings == sorted(ratings, reverse=True)


def test_exclude_and_limit(conn):
    first = search_shoes(conn, use="casual", limit=3)
    more = search_shoes(conn, use="casual", exclude_ids=[r["id"] for r in first], limit=3)
    assert not {r["id"] for r in first} & {r["id"] for r in more}
    assert len(first) == 3


def test_impossible_filters_return_empty(conn):
    assert search_shoes(conn, use="office", max_price=10) == []


def test_semantic_search_light_shoes_for_monsoon(conn):
    rows = search_shoes(conn, query="light shoes for monsoon", use="sports", limit=5)
    assert rows
    # Top matches should emphasize lightweight build and/or grippy/breathable traits for monsoon
    descriptions = [r["description"].lower() for r in rows]
    assert any("lightweight" in d or "grippy" in d or "breathable" in d for d in descriptions)


def test_semantic_search_with_category_and_traits(conn):
    rows = search_shoes(conn, category="apparel", query="breathable summer wear", limit=5)
    assert rows
    assert all(r["category"] == "apparel" for r in rows)


def test_fts_table_syncs_on_new_product(conn):
    conn.execute(
        "INSERT INTO shoes (id, name, brand, price, use_type, color, rating, image, description, category) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (9999, "Monsoon Pro Shield", "AquaTech", 4999, "sports", "black", 4.8, "img/9999.jpg",
         "A waterproof shoe built with ultra grippy outsole for heavy monsoon downpours.", "shoes")
    )
    conn.commit()
    rows = search_shoes(conn, query="heavy monsoon downpour", limit=3)
    assert rows and rows[0]["id"] == 9999
    conn.execute("DELETE FROM shoes WHERE id = 9999")
    conn.commit()
