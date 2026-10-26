from app.validators import Facts, strip_ungrounded, validate

SHOE = {"name": "Nike Runner", "brand": "Nike", "price": 4999, "color": "black", "rating": 4.2,
        "sizes_in_stock": [8.0, 9.0]}
BRANDS = {"Nike", "Clarks", "Red Tape"}
COLORS = {"black", "red", "navy"}


def facts(**kw):
    return Facts(products=[SHOE], brands=BRANDS, colors=COLORS, check_sizes=True, **kw)


def test_grounded_reply_passes():
    assert not validate("The Nike Runner is black and costs ₹4,999. It's rated 4.2 and comes in size 9.", facts())


def test_wrong_price_flagged_in_all_formats():
    for txt in ("It costs ₹3,999.", "Only Rs. 3999!", "About 3999 rupees."):
        assert validate(txt, facts()), txt


def test_other_brand_color_rating_size_flagged():
    assert validate("Clarks makes a better one.", facts())
    assert validate("It also comes in navy.", facts())
    assert validate("Rated 4.9 by everyone.", facts())
    assert validate("It's available in size 11.", facts())


def test_negated_size_is_not_a_claim():
    assert not validate("Size 11 isn't in stock.", facts())


def test_brand_name_not_misread_as_color():
    f = Facts(products=[{**SHOE, "brand": "Red Tape", "name": "Red Tape Oxford"}], brands=BRANDS, colors=COLORS)
    assert not validate("The Red Tape Oxford is black.", f)


def test_strip_removes_only_bad_sentences():
    out = strip_ungrounded("It costs ₹10. It is black and light.", facts())
    assert out == "It is black and light."


def test_extra_amounts_allowed():
    assert not validate("That's within your ₹5,500 budget.", facts(extra_amounts={5500}))
