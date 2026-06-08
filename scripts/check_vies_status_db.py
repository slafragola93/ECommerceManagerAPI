"""Diagnostica colonna orders.vies_status su MySQL."""
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

ORDER_ID = int(sys.argv[1]) if len(sys.argv) > 1 else None

url = (
    f"mysql+pymysql://{os.environ.get('DATABASE_MAIN_USER')}:"
    f"{os.environ.get('DATABASE_MAIN_PASSWORD')}@"
    f"{os.environ.get('DATABASE_MAIN_ADDRESS')}:"
    f"{os.environ.get('DATABASE_MAIN_PORT')}/"
    f"{os.environ.get('DATABASE_MAIN_NAME')}"
)

engine = create_engine(url)

queries = [
    ("COLONNA", "SHOW COLUMNS FROM orders LIKE 'vies_status'"),
    (
        "DISTRIBUZIONE",
        "SELECT vies_status, COUNT(*) AS n FROM orders GROUP BY vies_status ORDER BY n DESC",
    ),
    (
        "ULTIMI 10",
        """
        SELECT id_order, vies_status, HEX(CAST(vies_status AS CHAR)) AS hex_val, updated_at
        FROM orders
        ORDER BY id_order DESC
        LIMIT 10
        """,
    ),
]

if ORDER_ID is not None:
    queries.append(
        (
            f"ORDINE {ORDER_ID}",
            f"""
            SELECT id_order, vies_status, HEX(CAST(vies_status AS CHAR)) AS hex_val,
                   LENGTH(CAST(vies_status AS CHAR)) AS len_val, updated_at
            FROM orders WHERE id_order = {ORDER_ID}
            """,
        )
    )

with engine.connect() as conn:
    for title, sql in queries:
        print(f"\n=== {title} ===")
        for row in conn.execute(text(sql)):
            print(dict(row._mapping))
