#!/usr/bin/env python3
"""
Script per creare fixtures con dati fittizi per tutte le tabelle del database.
"""

import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
import random
from faker import Faker

# Aggiungi il path del progetto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal, engine
from src.models import *

fake = Faker(['it_IT', 'en_US'])

def create_fixtures():
    """Crea tutte le fixtures per il database."""
    
    db = SessionLocal()
    
    try:
        print("🚀 Inizio creazione fixtures...")
        
        # 1. Creazione Paesi
        print("📍 Creazione paesi...")
        countries = []
        country_names = ['Italia', 'Francia', 'Germania', 'Spagna', 'Regno Unito', 'Stati Uniti', 'Canada', 'Australia']
        for name in country_names:
            country = Country(
                name=name,
                iso_code=fake.country_code()
            )
            db.add(country)
            countries.append(country)
        db.commit()
        print(f"✅ Creati {len(countries)} paesi")
        
        # 2. Creazione Lingue
        print("🌍 Creazione lingue...")
        languages = []
        lang_data = [
            {'name': 'Italiano', 'code': 'it'},
            {'name': 'Inglese', 'code': 'en'},
            {'name': 'Francese', 'code': 'fr'},
            {'name': 'Tedesco', 'code': 'de'},
            {'name': 'Spagnolo', 'code': 'es'}
        ]
        for lang in lang_data:
            language = Lang(
                name=lang['name'],
                iso_code=lang['code']
            )
            db.add(language)
            languages.append(language)
        db.commit()
        print(f"✅ Create {len(languages)} lingue")
        
        # 3. Creazione Ruoli
        print("👥 Creazione ruoli...")
        roles = []
        role_names = ['Admin', 'Manager', 'Operatore', 'Cliente', 'Venditore']
        for name in role_names:
            role = Role(
                name=name,
                permissions=random.choice(['r', 'rud', 'crud'])
            )
            db.add(role)
            roles.append(role)
        db.commit()
        print(f"✅ Creati {len(roles)} ruoli")
        
        # 4. Creazione Utenti
        print("👤 Creazione utenti...")
        users = []
        for i in range(20):
            user = User(
                username=fake.user_name(),
                email=fake.email(),
                password=fake.sha256(),
                firstname=fake.first_name(),
                lastname=fake.last_name(),
                is_active=True,
                date_add=datetime.now().date()
            )
            db.add(user)
            users.append(user)
        db.commit()
        print(f"✅ Creati {len(users)} utenti")
        
        # 5. Associazione Utenti-Ruoli
        print("🔗 Associazione utenti-ruoli...")
        for user in users:
            # Ogni utente ha 1-2 ruoli casuali
            user_roles_count = random.randint(1, 2)
            selected_roles = random.sample(roles, user_roles_count)
            for role in selected_roles:
                # Usiamo la tabella di associazione direttamente
                from src.models.relations.relations import user_roles
                stmt = user_roles.insert().values(
                    id_user=user.id_user,
                    id_role=role.id_role
                )
                db.execute(stmt)
        db.commit()
        print("✅ Associazioni utenti-ruoli create")
        
        # 6. Creazione Clienti
        print("🛒 Creazione clienti...")
        customers = []
        for i in range(50):
            customer = Customer(
                email=fake.email(),
                firstname=fake.first_name(),
                lastname=fake.last_name(),
                id_lang=random.choice(languages).id_lang,
                id_origin=random.randint(1, 100),
                date_add=datetime.now().date()
            )
            db.add(customer)
            customers.append(customer)
        db.commit()
        print(f"✅ Creati {len(customers)} clienti")
        
        # 7. Creazione Indirizzi
        print("🏠 Creazione indirizzi...")
        addresses = []
        for customer in customers:
            # Ogni cliente ha 1-3 indirizzi
            address_count = random.randint(1, 3)
            for i in range(address_count):
                address = Address(
                    id_customer=customer.id_customer,
                    id_country=random.choice(countries).id_country,
                    firstname=customer.firstname,
                    lastname=customer.lastname,
                    address1=fake.street_address(),
                    city=fake.city(),
                    postcode=fake.postcode(),
                    phone=fake.phone_number(),
                    company=fake.company() if random.choice([True, False]) else None,
                    vat=fake.bothify('IT###########') if random.choice([True, False]) else None,
                    date_add=datetime.now().date()
                )
                db.add(address)
                addresses.append(address)
        db.commit()
        print(f"✅ Creati {len(addresses)} indirizzi")
        
        # 8. Creazione Categorie
        print("📂 Creazione categorie...")
        categories = []
        category_names = ['Elettronica', 'Abbigliamento', 'Casa e Giardino', 'Sport', 'Libri', 'Giochi', 'Beauty', 'Auto']
        for name in category_names:
            category = Category(
                name=name,
                id_origin=random.randint(1, 100)
            )
            db.add(category)
            categories.append(category)
        db.commit()
        print(f"✅ Create {len(categories)} categorie")
        
        # 9. Creazione Marchi
        print("🏷️ Creazione marchi...")
        brands = []
        brand_names = ['Apple', 'Samsung', 'Nike', 'Adidas', 'Sony', 'LG', 'Canon', 'Dell', 'HP', 'Microsoft']
        for name in brand_names:
            brand = Brand(
                name=name,
                id_origin=random.randint(1, 100)
            )
            db.add(brand)
            brands.append(brand)
        db.commit()
        print(f"✅ Creati {len(brands)} marchi")
        
        # 10. Creazione Tag
        print("🏷️ Creazione tag...")
        tags = []
        tag_names = ['novità', 'sconto', 'premium', 'ecologico', 'made in italy', 'tecnologia', 'design', 'qualità']
        for name in tag_names:
            tag = Tag(
                name=name,
                id_origin=random.randint(1, 100)
            )
            db.add(tag)
            tags.append(tag)
        db.commit()
        print(f"✅ Creati {len(tags)} tag")
        
        # 11. Creazione Prodotti
        print("📦 Creazione prodotti...")
        products = []
        for i in range(100):
            product = Product(
                name=fake.catch_phrase(),
                sku=fake.bothify('SKU-####-????'),
                type=random.choice(['simple', 'variable', 'grouped']),
                id_category=random.choice(categories).id_category,
                id_brand=random.choice(brands).id_brand,
                id_origin=random.randint(1, 100)
            )
            db.add(product)
            products.append(product)
        db.commit()
        print(f"✅ Creati {len(products)} prodotti")
        
        # 12. Associazione Prodotti-Tag
        print("🔗 Associazione prodotti-tag...")
        for product in products:
            # Ogni prodotto ha 1-3 tag casuali
            tag_count = random.randint(1, 3)
            selected_tags = random.sample(tags, tag_count)
            for tag in selected_tags:
                # Usiamo la tabella di associazione direttamente
                from src.models.relations.relations import product_tags
                stmt = product_tags.insert().values(
                    id_product=product.id_product,
                    id_tag=tag.id_tag
                )
                db.execute(stmt)
        db.commit()
        print("✅ Associazioni prodotti-tag create")
        
        # 13. Creazione Piattaforme
        print("🖥️ Creazione piattaforme...")
        platforms = []
        platform_names = ['Shopify', 'WooCommerce', 'Magento', 'PrestaShop', 'Amazon', 'eBay']
        for name in platform_names:
            platform = Platform(
                name=name,
                url=f"https://{name.lower()}.com",
                api_key=fake.sha256()
            )
            db.add(platform)
            platforms.append(platform)
        db.commit()
        print(f"✅ Create {len(platforms)} piattaforme")
        
        # 14. Creazione Sezionali
        print("📊 Creazione sezionali...")
        sectionals = []
        sectional_names = ['Nord', 'Sud', 'Centro', 'Est', 'Ovest', 'Online']
        for name in sectional_names:
            sectional = Sectional(
                name=name
            )
            db.add(sectional)
            sectionals.append(sectional)
        db.commit()
        print(f"✅ Creati {len(sectionals)} sezionali")
        
        # 15. Creazione Stati Ordine
        print("📋 Creazione stati ordine...")
        order_states = []
        state_names = ['Nuovo', 'In Elaborazione', 'Spedito', 'Consegnato', 'Annullato', 'Rimborsato']
        for name in state_names:
            order_state = OrderState(
                name=name
            )
            db.add(order_state)
            order_states.append(order_state)
        db.commit()
        print(f"✅ Creati {len(order_states)} stati ordine")
        
        # 16. Creazione Corrieri
        print("🚚 Creazione corrieri...")
        carriers = []
        carrier_names = ['DHL', 'UPS', 'FedEx', 'TNT', 'Poste Italiane', 'Bartolini', 'GLS']
        for name in carrier_names:
            carrier = Carrier(
                name=name,
                id_origin=random.randint(1, 100)
            )
            db.add(carrier)
            carriers.append(carrier)
        db.commit()
        print(f"✅ Creati {len(carriers)} corrieri")
        
        # 17. Creazione API Corrieri
        print("🔌 Creazione API corrieri...")
        carrier_apis = []
        for carrier in carriers:
            carrier_api = CarrierApi(
                name=f"API {carrier.name}",
                account_number=random.randint(100000, 999999),
                password=fake.password(),
                site_id=fake.bothify('SITE-####'),
                national_service=f"National {carrier.name}",
                international_service=f"International {carrier.name}",
                is_active=True,
                api_key=fake.sha256()
            )
            db.add(carrier_api)
            carrier_apis.append(carrier_api)
        db.commit()
        print(f"✅ Create {len(carrier_apis)} API corrieri")
        
        # 18. Creazione Stati Spedizione
        print("📦 Creazione stati spedizione...")
        shipping_states = []
        shipping_state_names = ['Preparazione', 'In Transito', 'In Consegna', 'Consegnato', 'Ritirato', 'Fallito']
        for name in shipping_state_names:
            shipping_state = ShippingState(
                name=name
            )
            db.add(shipping_state)
            shipping_states.append(shipping_state)
        db.commit()
        print(f"✅ Creati {len(shipping_states)} stati spedizione")
        
        # 19. Creazione Tasse
        print("💰 Creazione tasse...")
        taxes = []
        for country in countries:
            tax = Tax(
                name=f"IVA {country.name}",
                percentage=random.randint(5, 25),
                id_country=country.id_country,
                is_default=1 if country.name == 'Italia' else 0,
                code=f"IVA{random.randint(10, 99)}",
                note=f"Imposta sul valore aggiunto per {country.name}",
                electronic_code=f"E{random.randint(100, 999)}"
            )
            db.add(tax)
            taxes.append(tax)
        db.commit()
        print(f"✅ Create {len(taxes)} tasse")
        
        # 20. Creazione Pagamenti
        print("💳 Creazione pagamenti...")
        payments = []
        payment_methods = ['Carta di Credito', 'PayPal', 'Bonifico', 'Contrassegno', 'Apple Pay', 'Google Pay']
        for method in payment_methods:
            payment = Payment(
                name=method,
                is_complete_payment=random.choice([True, False])
            )
            db.add(payment)
            payments.append(payment)
        db.commit()
        print(f"✅ Creati {len(payments)} pagamenti")
        
        # 21. Creazione Ordini
        print("🛍️ Creazione ordini...")
        orders = []
        for i in range(200):
            customer = random.choice(customers)
            customer_addresses = [addr for addr in addresses if addr.id_customer == customer.id_customer]
            
            order = Order(
                id_origin=random.randint(1, 100),
                id_customer=customer.id_customer,
                id_platform=random.choice(platforms).id_platform,
                id_sectional=random.choice(sectionals).id_sectional,
                id_payment=random.choice(payments).id_payment,
                id_address_invoice=random.choice(customer_addresses).id_address,
                id_address_delivery=random.choice(customer_addresses).id_address,
                id_order_state=random.choice(order_states).id_order_state,
                is_invoice_requested=random.choice([True, False]),
                is_payed=random.choice([True, False]),
                payment_date=datetime.now().date() if random.choice([True, False]) else None,
                total_weight=round(random.uniform(0.1, 10), 2),
                total_price=round(random.uniform(50, 2000), 2),
                cash_on_delivery=round(random.uniform(0, 100), 2),
                insured_value=round(random.uniform(0, 1000), 2),
                privacy_note=fake.text(max_nb_chars=200) if random.choice([True, False]) else None,
                general_note=fake.text(max_nb_chars=200) if random.choice([True, False]) else None,
                delivery_date=datetime.now().date() + timedelta(days=random.randint(1, 30)) if random.choice([True, False]) else None,
                date_add=datetime.now().date() - timedelta(days=random.randint(1, 365))
            )
            db.add(order)
            orders.append(order)
        db.commit()
        print(f"✅ Creati {len(orders)} ordini")
        
        # 22. Creazione Dettagli Ordine
        print("📋 Creazione dettagli ordine...")
        order_details = []
        for order in orders:
            # Ogni ordine ha 1-5 prodotti
            detail_count = random.randint(1, 5)
            selected_products = random.sample(products, detail_count)
            
            for product in selected_products:
                quantity = random.randint(1, 10)
                price = round(random.uniform(10, 500), 2)
                
                order_detail = OrderDetail(
                    id_order=order.id_order,
                    id_product=product.id_product,
                    id_origin=random.randint(1, 100),
                    id_tax=random.choice(taxes).id_tax,
                    product_name=product.name,
                    product_reference=product.sku,
                    product_qty=quantity,
                    product_weight=round(random.uniform(0.1, 5), 2),
                    product_price=price,
                    reduction_percent=round(random.uniform(0, 20), 2),
                    reduction_amount=round(random.uniform(0, 50), 2),
                    rda=fake.bothify('RDA-####')
                )
                db.add(order_detail)
                order_details.append(order_detail)
        db.commit()
        print(f"✅ Creati {len(order_details)} dettagli ordine")
        
        # 23. Creazione Pacchi Ordine
        print("📦 Creazione pacchi ordine...")
        order_packages = []
        for order in orders:
            # Ogni ordine ha 1-3 pacchi
            package_count = random.randint(1, 3)
            for i in range(package_count):
                order_package = OrderPackage(
                    id_order=order.id_order,
                    height=round(random.uniform(10, 100), 2),
                    width=round(random.uniform(10, 100), 2),
                    depth=round(random.uniform(5, 50), 2),
                    weight=round(random.uniform(0.5, 20), 2),
                    value=round(random.uniform(10, 1000), 2)
                )
                db.add(order_package)
                order_packages.append(order_package)
        db.commit()
        print(f"✅ Creati {len(order_packages)} pacchi ordine")
        
        # 24. Creazione Spedizioni
        print("🚚 Creazione spedizioni...")
        shipments = []
        for order_package in order_packages:
            shipment = Shipping(
                id_carrier_api=random.choice(carrier_apis).id_carrier_api,
                id_shipping_state=random.choice(shipping_states).id_shipping_state,
                id_tax=random.choice(taxes).id_tax,
                tracking=fake.bothify('TRK-####-????'),
                weight=order_package.weight,
                price_tax_incl=round(random.uniform(5, 50), 2),
                price_tax_excl=round(random.uniform(4, 40), 2),
                shipping_message=fake.text(max_nb_chars=200) if random.choice([True, False]) else None,
                date_add=datetime.now().date()
            )
            db.add(shipment)
            shipments.append(shipment)
        db.commit()
        print(f"✅ Create {len(shipments)} spedizioni")
        
        # 25. Creazione Fatture
        print("🧾 Creazione fatture...")
        invoices = []
        for order in orders:
            if random.choice([True, False]):  # Solo alcuni ordini hanno fattura
                invoice = Invoice(
                    id_order=order.id_order,
                    id_customer=order.id_customer,
                    id_payment=order.id_payment,
                    id_address_invoice=order.id_address_invoice,
                    id_address_delivery=order.id_address_delivery,
                    invoice_status=random.choice(['draft', 'sent', 'paid', 'cancelled']),
                    note=fake.text(max_nb_chars=150) if random.choice([True, False]) else None,
                    payed=random.choice([True, False]),
                    document_number=random.randint(1000, 9999),
                    date_add=datetime.now().date()
                )
                db.add(invoice)
                invoices.append(invoice)
        db.commit()
        print(f"✅ Create {len(invoices)} fatture")
        
        # 26. Creazione Documenti Ordine
        print("📄 Creazione documenti ordine...")
        order_documents = []
        for order in orders:
            if random.choice([True, False]):  # Solo alcuni ordini hanno documenti
                order_document = OrderDocument(
                    id_order=order.id_order,
                    id_customer=order.id_customer,
                    id_sectional=order.id_sectional,
                    id_address_invoice=order.id_address_invoice,
                    id_address_delivery=order.id_address_delivery,
                    id_tax=random.choice(taxes).id_tax,
                    document_number=fake.bothify('DOC-####-????'),
                    type_document=random.choice(['invoice', 'delivery_note', 'receipt']),
                    total_weight=order.total_weight,
                    total_price=order.total_price,
                    delivery_price=round(random.uniform(5, 50), 2),
                    note=fake.text(max_nb_chars=200) if random.choice([True, False]) else None,
                    date_add=datetime.now().date()
                )
                db.add(order_document)
                order_documents.append(order_document)
        db.commit()
        print(f"✅ Creati {len(order_documents)} documenti ordine")
        
        # 27. Creazione Storico Ordini
        print("📊 Creazione storico ordini...")
        for order in orders:
            # Ogni ordine ha 2-4 stati nella cronologia
            state_count = random.randint(2, 4)
            selected_states = random.sample(order_states, state_count)
            
            for i, state in enumerate(selected_states):
                # Usiamo la tabella di associazione direttamente
                from src.models.relations.relations import orders_history
                stmt = orders_history.insert().values(
                    id_order=order.id_order,
                    id_order_state=state.id_order_state
                )
                db.execute(stmt)
        db.commit()
        print("✅ Storico ordini creato")
        
        # 28. Creazione Messaggi
        print("💬 Creazione messaggi...")
        messages = []
        for i in range(100):
            message = Message(
                id_user=random.choice(users).id_user,
                message=fake.text(max_nb_chars=500)
            )
            db.add(message)
            messages.append(message)
        db.commit()
        print(f"✅ Creati {len(messages)} messaggi")
        
        # 29. Creazione Configurazioni
        print("⚙️ Creazione configurazioni...")
        configurations = []
        config_keys = [
            'site_name', 'site_email', 'default_currency', 'tax_rate', 
            'shipping_cost', 'free_shipping_threshold', 'order_timeout'
        ]
        for key in config_keys:
            configuration = Configuration(
                name=key,
                value=fake.word() if key == 'site_name' else str(random.randint(1, 100)),
                id_lang=random.choice(languages).id_lang
            )
            db.add(configuration)
            configurations.append(configuration)
        db.commit()
        print(f"✅ Create {len(configurations)} configurazioni")
        
        print("\n🎉 Tutte le fixtures sono state create con successo!")
        print(f"📊 Riepilogo dati creati:")
        print(f"   - Paesi: {len(countries)}")
        print(f"   - Lingue: {len(languages)}")
        print(f"   - Ruoli: {len(roles)}")
        print(f"   - Utenti: {len(users)}")
        print(f"   - Clienti: {len(customers)}")
        print(f"   - Indirizzi: {len(addresses)}")
        print(f"   - Categorie: {len(categories)}")
        print(f"   - Marchi: {len(brands)}")
        print(f"   - Tag: {len(tags)}")
        print(f"   - Prodotti: {len(products)}")
        print(f"   - Piattaforme: {len(platforms)}")
        print(f"   - Sezionali: {len(sectionals)}")
        print(f"   - Stati Ordine: {len(order_states)}")
        print(f"   - Corrieri: {len(carriers)}")
        print(f"   - API Corrieri: {len(carrier_apis)}")
        print(f"   - Stati Spedizione: {len(shipping_states)}")
        print(f"   - Tasse: {len(taxes)}")
        print(f"   - Pagamenti: {len(payments)}")
        print(f"   - Ordini: {len(orders)}")
        print(f"   - Dettagli Ordine: {len(order_details)}")
        print(f"   - Pacchi Ordine: {len(order_packages)}")
        print(f"   - Spedizioni: {len(shipments)}")
        print(f"   - Fatture: {len(invoices)}")
        print(f"   - Documenti Ordine: {len(order_documents)}")
        print(f"   - Messaggi: {len(messages)}")
        print(f"   - Configurazioni: {len(configurations)}")
        
    except Exception as e:
        print(f"❌ Errore durante la creazione delle fixtures: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_fixtures()
