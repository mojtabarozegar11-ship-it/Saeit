"""Fixed USD promotions and private-file choices for MojPlayWin books.

Paths are relative to the private server directory
/home/zomorod2/MojPlayWin_Private_Assets, never public download URLs.
Original prices and savings are explicitly seller-authorized.
"""
from decimal import Decimal

DISCOUNT_BOOKS = (
    {
        "sku": "chess-improvement-final-2026",
        "title": "The Science and Practice of Chess Improvement",
        "original_usd": Decimal("30.00"),
        "sale_usd": Decimal("7.50"),
        "savings_usd": Decimal("22.50"),
        "discount_percent": 75,
        # Do not deliver the similarly named editorial working draft.
        "private_pdf": "store/chess-improvement/MojPlayWin_Chess_Grandmaster_Final_Covered_2026.pdf",
    },
    {
        "sku": "taniya-little-baker-worms",
        "title": "Taniya and the Little Baker Worms",
        "original_usd": Decimal("20.00"),
        "sale_usd": Decimal("2.00"),
        "savings_usd": Decimal("18.00"),
        "discount_percent": 90,
        "private_pdf": "taniya-little-baker-worms/Taniya_and_the_Little_Baker_Worms.pdf",
    },
)

for book in DISCOUNT_BOOKS:
    assert book["original_usd"] - book["sale_usd"] == book["savings_usd"]
    assert int(book["savings_usd"] * 100 / book["original_usd"]) == book["discount_percent"]
