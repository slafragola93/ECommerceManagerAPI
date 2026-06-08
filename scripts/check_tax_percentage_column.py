"""Diagnostica colonna taxes.percentage su MySQL (BE-ALIQ-05)."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

url = (
    f"mysql+pymysql://{os.environ.get('DATABASE_MAIN_USER')}:"
    f"{os.environ.get('DATABASE_MAIN_PASSWORD')}@"
    f"{os.environ.get('DATABASE_MAIN_ADDRESS')}:"
    f"{os.environ.get('DATABASE_MAIN_PORT')}/"
    f"{os.environ.get('DATABASE_MAIN_NAME')}"
)

engine = create_engine(url)

with engine.connect() as conn:
    row = conn.execute(text("SHOW COLUMNS FROM taxes LIKE 'percentage'")).fetchone()
    if not row:
        print("❌ Colonna taxes.percentage non trovata")
    else:
        col_type = row[1]
        print(f"taxes.percentage type: {col_type}")
        if "int" in str(col_type).lower():
            print(
                "ERROR: Colonna ancora INTEGER - 25.5 viene arrotondato a 26.\n"
                "Fix: alembic upgrade head\n"
                "oppure: python scripts/setup_initial.py"
            )
        else:
            print("OK: Colonna DECIMAL/NUMERIC - decimali supportati.")
