import sqlite3


def get_size(conn: sqlite3.Connection, user_id: str) -> float | None:
    row = conn.execute("SELECT size FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    return row["size"] if row else None


def save_size(conn: sqlite3.Connection, user_id: str, size: float) -> None:
    conn.execute(
        "INSERT INTO profiles (user_id, size) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET size = excluded.size", (user_id, size)
    )


def forget(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))


def load_profile(conn: sqlite3.Connection, user_id: str):
    from app.profile.model import Fact, Profile

    rows = conn.execute("SELECT key, value, status FROM profile_facts WHERE user_id = ?", (user_id,))
    return Profile([Fact(r["key"], r["value"], r["status"]) for r in rows])


def save_profile(conn: sqlite3.Connection, user_id: str, profile) -> None:
    conn.execute("DELETE FROM profile_facts WHERE user_id = ?", (user_id,))
    conn.executemany(
        "INSERT INTO profile_facts (user_id, key, value, status) VALUES (?,?,?,?)",
        [(user_id, f.key, f.value, f.status) for f in profile.facts],
    )
    conn.commit()


def forget_all(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM profile_facts WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
    conn.commit()
