from sqlalchemy import text

from src import Category, Brand, Customer, Payment, Tag


def get_ids_origin(db, model):
    ids_origin = db.query(model.id_origin).all()
    # Estrae gli id_origin da ciascuna tupla nel risultato
    ids_origin_list = [id[0] for id in ids_origin]
    return ids_origin_list


def get_id_by_id_origin(db, model, column_name, id_origin):
    id = db.query(getattr(model, column_name)). \
        filter(model.id_origin == id_origin). \
        first()
    if id:
        return id[0]
    return 0


def retrieve_category_by_id_origin(db, id_category):
    id_category = db.query(Category.id_category). \
        filter(Category.id_origin == id_category). \
        first()
    if id_category:
        return id_category[0]
    return 0


def retrieve_brand_by_id_origin(db, id_brand):
    id_brand = db.query(Brand.id_brand). \
        filter(Brand.id_origin == id_brand). \
        first()
    if id_brand:
        return id_brand[0]
    return 0


def retrieve_customer_by_id_origin(db, id_customer):
    id_customer = db.query(Customer.id_customer). \
        filter(Customer.id_origin == id_customer). \
        first()
    if id_customer:
        return id_customer[0]
    return 0


def retrieve_payment_methods(db):
    payment_methods = db.query(Payment.name).all()
    payment_names = [method[0] for method in payment_methods]
    return payment_names


def retrieve_tags(db):
    results = db.query(Tag.name).all()
    tags = [tag[0] for tag in results]
    return tags


def retrieve_product_tags(db):
    results = db.execute(text("SELECT id_product, id_tag FROM product_tags"))
    product_tags = [product_tag[0] for product_tag in results]
    return product_tags


def insert_product_tags(db, id_product, id_tag):
    sql_query = text("INSERT INTO product_tags (id_product, id_tag) VALUES (:id_product, :id_tag)")
    db.execute(sql_query, {'id_product': id_product, 'id_tag': id_tag})
    db.commit()
