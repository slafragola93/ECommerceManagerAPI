from sqlalchemy import Table, select
from .setup import *
from .functions import retrieve_payment_methods
from src.models import Payment

print("Inizio script...")
# python -m scripts.payment_method_script
orders_ps_table = Table('ww_ps_orders', metadata, autoload_with=src_engine)


connessione_ps = src_engine.connect()
connessione_main = dest_engine.connect()

payments_already_added = retrieve_payment_methods(dest_session)

query = select(
    orders_ps_table.c.payment,
).distinct().where(
    orders_ps_table.c.payment.not_in(payments_already_added)
)


payments_prestashop = connessione_ps.execute(query).fetchall()
connessione_ps.close()

#
print(f"Numero di metodi di pagamento da importare: {len(payments_prestashop)}")
try:
    payment_mappings = [{'name': payment.payment} for payment in payments_prestashop]

    dest_session.bulk_insert_mappings(Payment, payment_mappings)
    dest_session.commit()
except Exception as e:
    # In caso di errore, esegue il rollback delle modifiche
    dest_session.rollback()
    print(f"Si è verificato un errore durante l'importazione dei corrieri: {e}")
    exit()
print(
    f"Numero di metodi di pagamento importati: {len(payments_prestashop)}")

connessione_main.close()
print("Script metodi di pagamento terminato con successo")