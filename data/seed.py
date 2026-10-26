"""Generate a synthetic catalog (deterministic): 300 shoes, then apparel and accessories. Run: python -m data.seed"""
import random

from app.catalog.db import DB_PATH, connect, init_db

BRANDS = {
    "sports": ["Nike", "Adidas", "Puma", "ASICS", "Reebok", "Skechers"],
    "office": ["Clarks", "Bata", "Red Tape", "Hush Puppies", "Woodland"],
    "casual": ["Converse", "Vans", "Puma", "Skechers", "Crocs", "New Balance"],
}
MODELS = {
    "sports": ["Runner", "Sprint", "Trail", "Court Pro", "Flex Train", "Aero"],
    "office": ["Oxford", "Derby", "Loafer", "Brogue", "Formal Slip-on"],
    "casual": ["Classic", "Street", "Canvas Low", "Walker", "Cloud"],
}
COLORS = ["black", "white", "navy", "grey", "brown", "red", "olive", "tan"]
PRICE_RANGE = {"sports": (1800, 9500), "office": (1500, 7000), "casual": (1000, 6000)}
TRAITS = {
    "sports": ["cushioned midsole", "breathable mesh upper", "lightweight build", "grippy outsole"],
    "office": ["genuine leather upper", "padded insole", "classic stitching", "slip-resistant sole"],
    "casual": ["everyday comfort", "flexible sole", "easy slip-on fit", "soft lining"],
}

# Apparel sizes are stored as 1..6 (XS S M L XL XXL); accessories are one size, stored as 0.
APPAREL = {
    "sports": (["Nike", "Adidas", "Puma", "Reebok", "Decathlon"], ["Running T-Shirt", "Training Shorts", "Track Jacket", "Compression Tee", "Hoodie"]),
    "office": (["Van Heusen", "Allen Solly", "Peter England", "Raymond", "Arrow"], ["Formal Shirt", "Chinos", "Blazer", "Trousers", "Polo Shirt"]),
    "casual": (["Levis", "Roadster", "Wrogn", "Flying Machine", "Pepe Jeans"], ["Graphic Tee", "Denim Jeans", "Casual Shirt", "Sweatshirt", "Shorts"]),
}
APPAREL_PRICE = {"sports": (799, 3999), "office": (999, 5999), "casual": (699, 3999)}
APPAREL_TRAITS = {
    "sports": ["moisture-wicking fabric", "stretch fit", "breathable weave", "reflective detailing"],
    "office": ["wrinkle-resistant fabric", "tailored fit", "soft cotton blend", "classic collar"],
    "casual": ["soft cotton", "relaxed fit", "washed finish", "easy everyday wear"],
}
ACCESSORIES = {
    "sports": (["Nike", "Adidas", "Puma", "Decathlon", "Wildcraft"], ["Gym Bag", "Sports Cap", "Wristband", "Water Bottle", "Backpack"]),
    "office": (["Fossil", "Titan", "Skybags", "Hidesign", "Wildcraft"], ["Laptop Bag", "Leather Belt", "Wallet", "Watch", "Tie"]),
    "casual": (["Fossil", "Rayban", "Titan", "Skybags", "Puma"], ["Sunglasses", "Backpack", "Cap", "Watch", "Sling Bag"]),
}
ACCESSORY_TRAITS = ["sturdy build", "light to carry", "easy to clean", "classic design"]


def _add_extras(conn, seed_value: int, n_apparel: int, n_accessories: int, start_id: int) -> None:
    rnd = random.Random(seed_value + 1)  # separate stream: the shoes above never change
    next_id = start_id
    for category, count, table, price_range, traits in (
        ("apparel", n_apparel, APPAREL, APPAREL_PRICE, APPAREL_TRAITS),
        ("accessories", n_accessories, ACCESSORIES, None, None),
    ):
        for _ in range(count):
            use = rnd.choice(list(table))
            brand, model = rnd.choice(table[use][0]), rnd.choice(table[use][1])
            color = rnd.choice(COLORS)
            lo, hi = price_range[use] if price_range else (499, 7999)
            price = round(rnd.randint(lo, hi), -2) - 1
            trait = rnd.sample(traits[use] if traits else ACCESSORY_TRAITS, 2)
            conn.execute(
                "INSERT INTO shoes (id,name,brand,price,use_type,color,rating,image,description,category) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (next_id, f"{brand} {model}", brand, price, use, color, round(rnd.uniform(3.2, 4.9), 1), f"img/{next_id}.jpg",
                 f"A {color} {use} {model.lower()} with {trait[0]} and {trait[1]}.", category),
            )
            sizes = [float(s) for s in range(1, 7)] if category == "apparel" else [0.0]
            for size in sizes:
                conn.execute("INSERT INTO stock VALUES (?,?,?)", (next_id, size, rnd.choice([0, 0, 1, 3, 5, 8])))
            next_id += 1


def seed(n: int = 300, seed_value: int = 42, path=DB_PATH, extras: bool = True) -> None:
    rnd = random.Random(seed_value)
    conn = connect(path)
    conn.executescript("DROP TABLE IF EXISTS stock; DROP TABLE IF EXISTS shoes_fts; DROP TABLE IF EXISTS shoe_embeddings; DROP TABLE IF EXISTS shoes;")
    init_db(conn)
    for i in range(1, n + 1):
        use = rnd.choice(list(BRANDS))
        brand, model = rnd.choice(BRANDS[use]), rnd.choice(MODELS[use])
        color = rnd.choice(COLORS)
        lo, hi = PRICE_RANGE[use]
        price = round(rnd.randint(lo, hi), -2) - 1
        traits = rnd.sample(TRAITS[use], 2)
        conn.execute(
            "INSERT INTO shoes (id,name,brand,price,use_type,color,rating,image,description) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (i, f"{brand} {model}", brand, price, use, color,
             round(rnd.uniform(3.2, 4.9), 1), f"img/{i}.jpg",
             f"A {color} {use} shoe with {traits[0]} and {traits[1]}."),
        )
        for size in range(6, 13):
            conn.execute("INSERT INTO stock VALUES (?,?,?)", (i, float(size), rnd.choice([0, 0, 1, 3, 5, 8])))
    if extras:
        _add_extras(conn, seed_value, 90, 60, n + 1)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed()
    print(f"Seeded 300 shoes, 90 apparel and 60 accessories into {DB_PATH}")
