import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
load_dotenv()

# Configurazione del database sorgente (PS)
SRC_DB_URI = f'mysql+pymysql://{os.environ.get("DATABASE_LIVE_USER")}:{os.environ.get("DATABASE_LIVE_PASSWORD")}@{os.environ.get("DATABASE_LIVE_ADDRESS")}:{os.environ.get("DATABASE_LIVE_PORT")}/{os.environ.get("DATABASE_LIVE_NAME")}'
# Configurazione del database di destinazione
DEST_DB_URI = f'mysql+pymysql://{os.environ.get("DATABASE_MAIN_USER")}:{os.environ.get("DATABASE_MAIN_PASSWORD")}@{os.environ.get("DATABASE_MAIN_ADDRESS")}:{os.environ.get("DATABASE_MAIN_PORT")}/{os.environ.get("DATABASE_MAIN_NAME")}'

# Crea gli engine SQLAlchemy per entrambi i database
src_engine = create_engine(SRC_DB_URI)
dest_engine = create_engine(DEST_DB_URI)

# Prepara le sessioni per entrambi i database
SrcSession = sessionmaker(bind=src_engine)
DestSession = sessionmaker(bind=dest_engine)

src_session = SrcSession()
dest_session = DestSession()

#Recupera ultimo ID aggiunto
metadata = MetaData()
