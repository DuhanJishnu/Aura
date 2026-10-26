import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "shop.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS shoes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    price INTEGER NOT NULL,
    use_type TEXT NOT NULL CHECK (use_type IN ('sports','office','casual')),
    color TEXT NOT NULL,
    rating REAL NOT NULL DEFAULT 4.0,
    image TEXT,
    description TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'shoes'  -- shoes | apparel | accessories
);
CREATE TABLE IF NOT EXISTS stock (
    shoe_id INTEGER NOT NULL REFERENCES shoes(id),
    size REAL NOT NULL,
    qty INTEGER NOT NULL,
    PRIMARY KEY (shoe_id, size)
);
CREATE TABLE IF NOT EXISTS profiles (user_id TEXT PRIMARY KEY, size REAL);
CREATE TABLE IF NOT EXISTS profile_facts (
    user_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, status TEXT NOT NULL,
    PRIMARY KEY (user_id, key, value)
);
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY, user_id TEXT, total INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    order_id TEXT NOT NULL REFERENCES orders(id), shoe_id INTEGER NOT NULL,
    size REAL NOT NULL, price INTEGER NOT NULL, name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shoes_use ON shoes(use_type);
CREATE INDEX IF NOT EXISTS idx_stock_size ON stock(size, qty);

CREATE VIRTUAL TABLE IF NOT EXISTS shoes_fts USING fts5(
    id UNINDEXED,
    name,
    brand,
    description,
    use_type,
    category,
    color,
    tokenize = 'porter unicode61'
);

CREATE TABLE IF NOT EXISTS shoe_embeddings (
    shoe_id INTEGER PRIMARY KEY REFERENCES shoes(id),
    vector BLOB NOT NULL
);

CREATE TRIGGER IF NOT EXISTS shoes_ai AFTER INSERT ON shoes BEGIN
    INSERT INTO shoes_fts(id, name, brand, description, use_type, category, color)
    VALUES (new.id, new.name, new.brand, new.description, new.use_type, new.category, new.color);
END;

CREATE TRIGGER IF NOT EXISTS shoes_ad AFTER DELETE ON shoes BEGIN
    DELETE FROM shoes_fts WHERE id = old.id;
    DELETE FROM shoe_embeddings WHERE shoe_id = old.id;
END;

CREATE TRIGGER IF NOT EXISTS shoes_au AFTER UPDATE ON shoes BEGIN
    DELETE FROM shoes_fts WHERE id = old.id;
    INSERT INTO shoes_fts(id, name, brand, description, use_type, category, color)
    VALUES (new.id, new.name, new.brand, new.description, new.use_type, new.category, new.color);
END;
"""


def connect(path=DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(shoes)")}
    if "category" not in cols:  # a catalog built before categories existed: everything in it is a shoe
        conn.execute("ALTER TABLE shoes ADD COLUMN category TEXT NOT NULL DEFAULT 'shoes'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_shoes_category ON shoes(category, use_type)")

    # Sync shoes_fts if shoes exist but FTS table is not populated yet
    count_shoes = conn.execute("SELECT COUNT(*) FROM shoes").fetchone()[0]
    count_fts = conn.execute("SELECT COUNT(*) FROM shoes_fts").fetchone()[0]
    if count_shoes > 0 and count_fts == 0:
        conn.execute(
            "INSERT INTO shoes_fts(id, name, brand, description, use_type, category, color) "
            "SELECT id, name, brand, description, use_type, category, color FROM shoes"
        )
    conn.commit()
