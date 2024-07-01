import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd
import os

# Assumi che il setup e le funzioni siano definiti nei moduli indicati
from .setup import dest_engine, dest_session
from src.models import Tax

# Percorso del file CSV sul Desktop
# Percorso del file CSV sul Desktop
file_path = os.path.expanduser("~/Desktop/tax.csv")
# Carica il file CSV
try:
    df = pd.read_csv("C:/Users/webmarke22/Documents/GESTIONALE/fastApiProject/scripts/tax.csv", delimiter=";",
                     encoding="utf-8")
# Prova con il delimitatore ','
except pd.errors.ParserError:
    try:
        df = pd.read_csv("C:/Users/webmarke22/Documents/GESTIONALE/fastApiProject/scripts/tax.csv", delimiter=";",
                         encoding="utf-8")
    # Prova con il delimitatore ';'
    except Exception as e:
        print(f"Si è verificato un errore durante il caricamento del file CSV: {e}")
        exit()
except Exception as e:
    print(f"Si è verificato un errore durante il caricamento del file CSV: {e}")
    exit()

df = df.replace({np.nan: None})
# Creare il mapping per l'inserimento
taxes_mapping = df.to_dict(orient='records')

# Connessione al database
connessione_main = dest_engine.connect()

try:
    # Inserimento nella tabella Taxes
    dest_session.bulk_insert_mappings(Tax, taxes_mapping)
    dest_session.commit()
except Exception as e:
    # In caso di errore, esegue il rollback delle modifiche
    dest_session.rollback()
    print(f"Si è verificato un errore durante l'importazione delle tasse: {e}")
    exit()
finally:
    connessione_main.close()

print("Script di importazione delle tasse terminato con successo")
