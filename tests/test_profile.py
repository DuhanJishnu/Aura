from app.profile import store
from app.profile.model import Profile


def test_stated_beats_inferred_and_colors_exclude_each_other():
    p = Profile()
    p.set_color("black", True, "stated")
    p.set_color("black", True, "inferred")  # a guess must not downgrade a stated fact
    assert p.values("liked_color")[0].status == "stated"
    p.set_color("black", False, "stated")   # the user changes their mind
    assert not p.values("liked_color") and p.values("rejected_color")[0].value == "black"
    p.set_color("black", True, "inferred")  # a guess cannot undo a stated dislike
    assert not p.values("liked_color")


def test_single_valued_facts_replace(conn):
    p = Profile()
    p.set("undertone", "warm", "stated")
    p.set("undertone", "cool", "confirmed")
    assert [f.value for f in p.values("undertone")] == ["cool"]


def test_store_round_trip_and_forget(conn):
    p = Profile()
    p.set("undertone", "warm", "confirmed")
    p.set_color("tan", True, "inferred")
    store.save_profile(conn, "u1", p)
    store.save_size(conn, "u1", 9.0)
    loaded = store.load_profile(conn, "u1")
    assert {(f.key, f.value, f.status) for f in loaded.facts} == {("undertone", "warm", "confirmed"), ("liked_color", "tan", "inferred")}
    store.forget_all(conn, "u1")
    assert store.load_profile(conn, "u1").facts == [] and store.get_size(conn, "u1") is None
