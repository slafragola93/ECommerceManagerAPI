from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()
SQLALCHEMY_DATABASE_URL = \
    f'mysql+pymysql://{os.environ.get("DATABASE_MAIN_USER")}:{os.environ.get("DATABASE_MAIN_PASSWORD")}@{os.environ.get("DATABASE_MAIN_ADDRESS")}:{os.environ.get("DATABASE_MAIN_PORT")}/{os.environ.get("DATABASE_MAIN_NAME")}'


engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base per controllare il nostro DB
Base = declarative_base()


def get_db():
    """
        Generatore di sessione database.

        Crea una sessione database e la chiude automaticamente una volta completate le operazioni.
        È ideale per essere utilizzato con FastAPI come dipendenza per gestire la sessione al database.

        Yields:
            SessionLocal: Una sessione di SQLAlchemy aperta.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
