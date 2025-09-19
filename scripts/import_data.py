from sqlalchemy import Table, select, Column, Integer

from .functions import get_ids_origin, retrieve_brand_by_id_origin, retrieve_category_by_id_origin, \
    retrieve_customer_by_id_origin, get_id_by_id_origin
from .setup import *
from tqdm import tqdm
from src.models import Customer, Category, Brand, Product, Address, Carrier
from sqlalchemy import literal_column

#python -m scripts.import_data


feature_product_ps_table = Table('ww_ps_feature_product', metadata,
                                 Column('id', Integer, primary_key=True),
                                 Column('id_product', Integer),
                                 Column('id_feature_value', Integer)
                                 )


def get_feature_values_for_product(conn, product_id: int):
    global feature_product_ps_table
    query = select(feature_product_ps_table.c.id_feature_value).where(
        feature_product_ps_table.c.id_product == product_id)
    result = conn.execute(query)
    return [row.id_feature_value for row in result.fetchall()]


# Recupera gli id già presenti in DB
customer_ids_origin_already_added = get_ids_origin(dest_session, Customer)
customer_ps_table = Table('ww_ps_customer', metadata, autoload_with=src_engine)

# Costruisce la query per selezionare clienti non ancora aggiunti
connessione_ps = src_engine.connect()

#### IMPORT CUSTOMER #####
counter = 0
query = select(
    customer_ps_table.c.id_customer.label('id_origin'),
    customer_ps_table.c.id_lang,
    customer_ps_table.c.firstname,
    customer_ps_table.c.lastname,
    customer_ps_table.c.email
).where(customer_ps_table.c.id_customer.not_in(customer_ids_origin_already_added)) \
    .order_by(customer_ps_table.c.id_customer)

customers_prestashop = connessione_ps.execute(query).fetchall()

if not customers_prestashop:
    print("Nessun cliente da importare.")
else:
    try:
        for customer in tqdm(customers_prestashop, desc="Processing customers", unit="customer"):
            new_customer = Customer(
                id_origin=customer.id_origin,
                id_lang=customer.id_lang,
                firstname=customer.firstname,
                lastname=customer.lastname,
                email=customer.email
            )
            dest_session.add(new_customer)
            counter += 1
        dest_session.commit()
        print(
            f"Numero di clienti importati: {counter}")
    except Exception as e:
        # In caso di errore, esegue il rollback delle modifiche
        dest_session.rollback()
        print(f"Si è verificato un errore durante l'importazione dei clienti: {e}")
    # finally:
    #     dest_session.close()
###############################################
################# CATEGORIES ###############
counter = 0
categories_ids_origin_already_added = get_ids_origin(dest_session, Category)
category_ps_table = Table('ww_ps_category_lang', metadata, autoload_with=src_engine)
query = select(
    category_ps_table.c.id_category.label('id_origin'),
    category_ps_table.c.name,
) \
    .where(category_ps_table.c.id_lang == 1) \
    .where(category_ps_table.c.id_category.not_in(categories_ids_origin_already_added)) \
    .order_by(category_ps_table.c.id_category)

categories_prestashop = connessione_ps.execute(query).fetchall()

if not categories_prestashop:
    print("Nessuna categoria da importare.")
else:
    try:
        for category in tqdm(categories_prestashop, desc="Processing categories", unit="category"):
            new_category = Category(
                id_origin=category.id_origin,
                name=category.name
            )
            dest_session.add(new_category)
            counter += 1
        dest_session.commit()
        print(
            f"Numero di categorie importate: {len(categories_prestashop)}")
    except Exception as e:
        # In caso di errore, esegue il rollback delle modifiche
        dest_session.rollback()
        print(f"Si è verificato un errore durante l'importazione delle categorie: {e}")

###############################################
################# BRANDS ###############
counter = 0
brands_ids_origin_already_added = get_ids_origin(dest_session, Brand)
brand_ps_table = Table('ww_ps_manufacturer', metadata, autoload_with=src_engine)
query = select(
    brand_ps_table.c.id_manufacturer.label('id_origin'),
    brand_ps_table.c.name,
) \
    .where(brand_ps_table.c.id_manufacturer.not_in(brands_ids_origin_already_added)) \
    .order_by(brand_ps_table.c.id_manufacturer)

brands_prestashop = connessione_ps.execute(query).fetchall()


if not brands_prestashop:
    print("Nessun brand da importare.")
else:
    try:
        for brand in tqdm(brands_prestashop, desc="Processing brands", unit="brand"):
            new_brand = Brand(
                id_origin=brand.id_origin,
                name=brand.name
            )
            counter += 1
            dest_session.add(new_brand)

        dest_session.commit()
        print(f"Numero di brand importati: {len(brands_prestashop)}")
    except Exception as e:
        # In caso di errore, esegue il rollback delle modifiche
        dest_session.rollback()
        print(f"Si è verificato un errore durante l'importazione dei brand: {e}")

###############################################
################# PRODUCT ###############
counter = 0
products_ids_origin_already_added = get_ids_origin(dest_session, Product)

product_ps_table = Table('ww_ps_product', metadata, autoload_with=src_engine)
product_lang_ps_table = Table('ww_ps_product_lang', metadata, autoload_with=src_engine)

query = select(
    product_lang_ps_table.c.id_product.label('id_origin'),
    product_ps_table.c.id_category_default,
    product_ps_table.c.id_manufacturer,
    product_lang_ps_table.c.name,
    product_ps_table.c.reference
).select_from(
    product_lang_ps_table.join(product_ps_table, product_lang_ps_table.c.id_product == product_ps_table.c.id_product)
).where(
    product_lang_ps_table.c.id_lang == 1
).where(product_ps_table.c.id_product.not_in(products_ids_origin_already_added)).distinct()

products_prestashop = connessione_ps.execute(query).fetchall()

if not products_prestashop:
    print("Nessun prodotto da importare.")
else:
    try:
        for product in tqdm(products_prestashop, desc="Processing products", unit="product"):
            id_brand = retrieve_brand_by_id_origin(dest_session, product.id_manufacturer)
            id_category = retrieve_category_by_id_origin(dest_session, product.id_category_default)

            ## Per la categoria climatizzatori su PS, recuperiamo la tipologia
            """
                MONO => ID 230
                DUAL => ID 271
                TRIAL => ID 272
                QUADRI => ID 1289
                PENTA => ID 1661
            """
            if product.id_category_default == 702:

                id_feature_value = get_feature_values_for_product(src_session, product.id_origin)
                if 230 in id_feature_value:
                    type = "MONO"
                elif 271 in id_feature_value:
                    type = "DUAL"
                elif 272 in id_feature_value:
                    type = "TRIAL"
                elif 1289 in id_feature_value:
                    type = "QUADRI"
                elif 1661 in id_feature_value:
                    type = "PENTA"
            else:
                type = "ALTRO"
            new_product = Product(
                id_origin=product.id_origin,
                id_category=id_category if id_category != 0 else None,
                id_brand=id_brand if id_brand != 0 else None,
                name=product.name,
                sku=product.reference,
                type=type
            )
            dest_session.add(new_product)
            counter += 1

        dest_session.commit()
        print(f"Numero di prodotti importati: {counter}")
    except Exception as e:
        # In caso di errore, esegue il rollback delle modifiche
        dest_session.rollback()
        print(f"Si è verificato un errore durante l'importazione dei prodotti: {e}")

#### ADDRESS #######
counter = 0
address_ids_origin_already_added = get_ids_origin(dest_session, Address)

address_ps_table = Table('ww_ps_address', metadata, autoload_with=src_engine)
state_ps_table = Table('ww_ps_state', metadata, autoload_with=src_engine)

query = select(
    address_ps_table.c.id_address.label('id_origin'),
    address_ps_table.c.id_customer.label('id_origin_customer'),
    address_ps_table.c.id_country.label('id_origin_country'),
    address_ps_table.c.company,
    address_ps_table.c.firstname,
    address_ps_table.c.lastname,
    address_ps_table.c.address1,
    address_ps_table.c.address2,
    state_ps_table.c.name.label('name_state'),
    address_ps_table.c.postcode,
    address_ps_table.c.city,
    address_ps_table.c.phone,
    address_ps_table.c.phone_mobile.label('mobile_phone'),
    address_ps_table.c.vat_number.label('vat'),
    address_ps_table.c.dni,
    address_ps_table.c.pec,
    address_ps_table.c.sdi
).select_from(
    address_ps_table.join(state_ps_table, address_ps_table.c.id_state == state_ps_table.c.id_state)
).where(
    address_ps_table.c.id_address.not_in(address_ids_origin_already_added)
)


addresses_prestashop = connessione_ps.execute(query).fetchall()
if not addresses_prestashop:
    print("Nessun indirizzo da importare.")
else:
    try:
        for address in tqdm(addresses_prestashop, desc="Processing addresses", unit="address"):
            id_customer = retrieve_customer_by_id_origin(dest_session, address.id_origin_customer)

            new_address = Address(
                id_origin=address.id_origin,
                id_customer=id_customer,
                id_country=address.id_origin_country,
                company=address.company,
                firstname=address.firstname,
                lastname=address.lastname,
                address1=address.address1,
                address2=address.address2,
                state=address.name_state,
                postcode=address.postcode,
                city=address.city,
                phone=address.phone,
                mobile_phone=address.mobile_phone,
                vat=address.vat,
                dni=address.dni,
                pec=address.pec,
                sdi=address.sdi
            )
            dest_session.add(new_address)
            counter += 1

        dest_session.commit()
        print(f"Numero di indirizzi importati: {counter}")
    except Exception as e:
        # In caso di errore, esegue il rollback delle modifiche
        dest_session.rollback()
        print(f"Si è verificato un errore durante l'importazione degli indirizzi: {e}")

##### IMPORT CORRIERI #################
# carrier_ids_origin_already_added = get_ids_origin(dest_session, Carrier)
#
# carrier_ps_table = Table('ww_ps_carrier', metadata, autoload_with=src_engine)
#
# query = select(
#     carrier_ps_table.id_reference.label('id_origin'),
#     carrier_ps_table.name,
#     literal_column("0.0").label("min_weight"),
#     literal_column("0.0").label("max_weight"),
#     price
# ).where(
#     carrier_ps_table.id_carrier.not_in(carrier_ids_origin_already_added)
# )


print("Trasferimento completato.")