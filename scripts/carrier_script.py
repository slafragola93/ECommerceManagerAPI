from sqlalchemy import Table, select
from .setup import *
from .functions import get_ids_origin
from src.models import Carrier

print("Inizio script...")
# python -m scripts.carrier_script
carrier_ps_table = Table('ww_ps_carrier', metadata, autoload_with=src_engine)


connessione_ps = src_engine.connect()
connessione_main = dest_engine.connect()

ids_carrier_already_added = get_ids_origin(dest_session, Carrier)


query = select(
    carrier_ps_table.c.id_reference.label('id_origin'),
    carrier_ps_table.c.name
).distinct().where(
    carrier_ps_table.c.id_reference.not_in(ids_carrier_already_added)
)


carriers_prestashop = connessione_ps.execute(query).fetchall()
connessione_ps.close()

print(f"Numero di corrieri da importare: {len(carriers_prestashop)}")
try:
    carrier_mappings = [{'id_origin': carrier.id_origin, 'name': carrier.name} for carrier in carriers_prestashop]

    dest_session.bulk_insert_mappings(Carrier, carrier_mappings)
    dest_session.commit()
except Exception as e:
    # In caso di errore, esegue il rollback delle modifiche
    dest_session.rollback()
    print(f"Si è verificato un errore durante l'importazione dei corrieri: {e}")
    exit()
print(
    f"Numero di corrieri importati: {len(carriers_prestashop)}")

connessione_main.close()
print("Script corrieri terminato con successo")