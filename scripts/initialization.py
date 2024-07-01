from sqlalchemy import Table, select

from src import ShippingState, Role, Platform, Configuration
from .setup import *
from src.models import Country, Lang

# python -m scripts.initialization
country_lang_ps_table = Table('ww_ps_country_lang', metadata, autoload_with=src_engine)
country_ps_table = Table('ww_ps_country', metadata, autoload_with=src_engine)

connessione_ps = src_engine.connect()


###### COUNTRY ############

def get_ids_country(db):
    ids_country = db.query(Country.id_country).all()
    # Estrae gli id_country da ciascuna tupla nel risultato
    ids_country_list = [id[0] for id in ids_country]
    return ids_country_list


def get_ids_lang(db):
    ids_lang = db.query(Lang.id_lang).all()
    # Estrae gli id_country da ciascuna tupla nel risultato
    ids_lang_list = [id[0] for id in ids_lang]
    return ids_lang_list


def get_shipping_states_name(db):
    states = db.query(ShippingState.name).all()
    return [state[0] for state in states]


def get_roles(db):
    roles = db.query(Role.name).all()
    return [role[0] for role in roles]


def get_platforms(db):
    platforms = db.query(Platform.name).all()
    return [platform[0] for platform in platforms]


ids_country = get_ids_country(dest_session)

query = select(
    country_lang_ps_table.c.id_country,
    country_lang_ps_table.c.name,
    country_ps_table.c.iso_code
).select_from(
    country_lang_ps_table.join(country_ps_table, country_ps_table.c.id_country == country_lang_ps_table.c.id_country)
).where(
    country_lang_ps_table.c.id_lang == 1
) \
    .where(country_lang_ps_table.c.id_country.not_in(ids_country)).order_by(
    country_lang_ps_table.c.id_country
)

countries_prestashop = connessione_ps.execute(query).fetchall()
if not countries_prestashop:
    print("Nessun country da importare.")
else:
    try:
        for country in countries_prestashop:
            new_country = Country(
                id_country=country.id_country,
                name=country.name,
                iso_code=country.iso_code,
            )
            dest_session.add(new_country)

        dest_session.commit()
        print(
            f"Numero di paesi importati: {len(countries_prestashop)}")
    except Exception as e:
        # In caso di errore, esegue il rollback delle modifiche
        dest_session.rollback()
        print(f"Si è verificato un errore durante l'importazione dei paesu: {e}")

ids_lang = get_ids_lang(dest_session)
lang_ps_table = Table('ww_ps_lang', metadata, autoload_with=src_engine)

query = select(
    lang_ps_table.c.id_lang,
    lang_ps_table.c.name,
    lang_ps_table.c.iso_code
).where(lang_ps_table.c.id_lang.not_in(ids_lang)).order_by(
    lang_ps_table.c.id_lang
)

langs_prestashop = connessione_ps.execute(query).fetchall()
if not langs_prestashop:
    print("Nessuna lingua da importare.")
else:
    try:
        for lang in langs_prestashop:
            new_lang = Lang(
                id_lang=lang.id_lang,
                name=lang.name,
                iso_code=lang.iso_code,
            )
            dest_session.add(new_lang)

        dest_session.commit()
        print(
            f"Numero di lingue importate: {len(langs_prestashop)}")
    except Exception as e:
        # In caso di errore, esegue il rollback delle modifiche
        dest_session.rollback()
        print(f"Si è verificato un errore durante l'importazione delle lingue: {e}")

#### SHIPPING STATE ########
print("Importazione stati spedizione...")
shipping_states = ["In Attesa Del Tracking", "Tracking Assegnato", "In Attesa di Trasmissione", "Trasmessa",
                   "Presa In Carico",
                   "Partita", "In Transito", "In Consegna", "Consegnato"]
states_already_presents = get_shipping_states_name(dest_session)

try:
    for state in shipping_states:
        if state not in states_already_presents:
            shipping_state = ShippingState(
                name=state
            )
            dest_session.add(shipping_state)

    dest_session.commit()
    print("Stati Spedizione importati correttamente")
except Exception as e:
    # In caso di errore, esegue il rollback delle modifiche
    dest_session.rollback()
    print(f"Si è verificato un errore durante l'importazione degli stati: {e}")

### ROLES #####

roles = ["ADMIN", "USER", "ORDINI", "FATTURAZIONE", "PREVENTIVI"]
roles_already_presents = get_roles(dest_session)
try:
    for role in roles:
        if role not in roles_already_presents:
            role = Role(
                name=role,
                permissions="CRUD"
            )
            dest_session.add(role)

    dest_session.commit()
    print("Ruoli importati correttamente")
except Exception as e:
    # In caso di errore, esegue il rollback delle modifiche
    dest_session.rollback()
    print(f"Si è verificato un errore durante l'importazione dei ruoli: {e}")

### PLATFORM ####
platforms = ["Gestionale", "Prestashop"]
platforms_already_presents = get_platforms(dest_session)

try:
    for platform in platforms:
        if platform not in platforms_already_presents:
            platform = Platform(
                name=platform,
                url="",
                api_key=""
            )
            dest_session.add(platform)

    dest_session.commit()
    print("Piattaforme importate correttamente")
except Exception as e:
    # In caso di errore, esegue il rollback delle modifiche
    dest_session.rollback()
    print(f"Si è verificato un errore durante l'importazione delle Piattaforme: {e}")

### CONFIGURATION ####

configs = [
    # Italia
    {
        "id_lang": 1,
        "name": "P_IVA",
        "value": "IT08632861210"
    },
    # Inglese
    {
        "id_lang": 2,
        "name": "P_IVA",
        "value": "IT08632861210"
    },
    # Spagnolo
    {
        "id_lang": 3,
        "name": "P_IVA",
        "value": "IT08632861210"
    },
    # Francese
    {
        "id_lang": 4,
        "name": "P_IVA",
        "value": "FR09843083841"
    },
    # Tedesco
    {
        "id_lang": 5,
        "name": "P_IVA",
        "value": "DE336031431"
    },

]

configs_already_presents = dest_session.query(Configuration.name).all()
configs_already_presents = [config[0] for config in configs_already_presents]

try:
    for config in configs:
        if config not in configs_already_presents:
            config = Configuration(
                id_lang=config["id_lang"],
                name=config["name"],
                value=config["value"]
            )
            dest_session.add(config)

    dest_session.commit()
    print("Configurazioni importate correttamente")
except Exception as e:
    # In caso di errore, esegue il rollback delle modifiche
    dest_session.rollback()
    print(f"Si è verificato un errore durante l'importazione delle Configurazioni: {e}")
