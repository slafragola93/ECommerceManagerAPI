from datetime import date
from typing import Optional
from fastapi import HTTPException
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from .customer_repository import CustomerRepository
from ..models import Address, Country, Customer
from src.schemas.address_schema import *
from src.services import QueryUtils


class AddressRepository:
    """
    Repository indirizzi
    """

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self,
                page: int = 1, limit: int = 10,
                **kwargs
                ) -> AllAddressResponseSchema:
        """
        Recupera tutti gli indirizzi

        Returns:
            AllAddressResponseSchema: Tutti gli indirizzi
        """
        query = self.session.query(
            Address,
            Country,
            Customer
        ).order_by(desc(Address.id_address)).outerjoin(Country, Address.id_country == Country.id_country).outerjoin(Customer,
                                                                       Address.id_customer == Customer.id_customer)



        try:
            query = QueryUtils.filter_by_id(query, Address, 'id_address', kwargs.get('addresses_ids'))
            query = QueryUtils.filter_by_id(query, Address, 'id_origin', kwargs.get('origin_ids'))
            query = QueryUtils.filter_by_id(query, Customer, 'id_customer', kwargs.get('customers_ids'))
            query = QueryUtils.filter_by_id(query, Address, 'id_country', kwargs.get('countries_ids'))

            query = QueryUtils.filter_by_string(query, Address, 'state', kwargs.get('state'))
            query = QueryUtils.filter_by_string(query, Address, 'vat', kwargs.get('vat'))
            query = QueryUtils.filter_by_string(query, Address, 'dni', kwargs.get('dni'))
            query = QueryUtils.filter_by_string(query, Address, 'pec', kwargs.get('pec'))
            query = QueryUtils.filter_by_string(query, Address, 'sdi', kwargs.get('sdi'))

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")
        addresses_result = query.offset(QueryUtils.get_offset(limit, page)).limit(limit).all()
        return addresses_result

    def get_by_address(self,
                       city: str,
                       address: str,
                       country: int,
                       firstname: str,
                       postcode: str,
                       lastname: str) -> AddressResponseSchema:

        return self.session.query(Address).filter(Address.city == city.lower(),
                                                  Address.address1 == address.lower(),
                                                  Address.id_country == country,
                                                  Address.firstname == firstname.lower(),
                                                  Address.lastname == lastname.lower(),
                                                  Address.postcode == postcode).first()

    def get_count(self,
                  addresses_ids: Optional[str] = None,
                  origin_ids: Optional[str] = None,
                  customers_ids: Optional[str] = None,
                  countries_ids: Optional[str] = None,
                  state: Optional[str] = None,
                  vat: Optional[str] = None,
                  dni: Optional[str] = None,
                  pec: Optional[str] = None,
                  sdi: Optional[str] = None,
                  ) -> int:

        query = self.session.query(
            func.count(Address.id_address)
        ).outerjoin(Country, Address.id_country == Country.id_country).outerjoin(Customer,
                                                                       Address.id_customer == Customer.id_customer)
        try:
            query = QueryUtils.filter_by_id(query, Address, 'id_address', addresses_ids)
            query = QueryUtils.filter_by_id(query, Address, 'id_origin', origin_ids)
            query = QueryUtils.filter_by_id(query, Customer, 'id_customer', customers_ids)
            query = QueryUtils.filter_by_id(query, Address, 'id_country', countries_ids)

            query = QueryUtils.filter_by_string(query, Address, 'state', state)
            query = QueryUtils.filter_by_string(query, Address, 'vat', vat)
            query = QueryUtils.filter_by_string(query, Address, 'dni', dni)
            query = QueryUtils.filter_by_string(query, Address, 'pec', pec)
            query = QueryUtils.filter_by_string(query, Address, 'sdi', sdi)

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")

        total_count = query.scalar()

        return total_count

    def get_complete_address_by_id(self, _id: int) -> AddressResponseSchema:
        """
        Ottieni indirizzo per ID

        Args:
            _id (int): Indirizzo ID.

        Returns:
            AddressResponseSchema: Istanza dell'indirizzo.
        """

        return self.session.query(
            Address,
            Country,
            Customer
        ).outerjoin(Country, Address.id_country == Country.id_country).outerjoin(Customer,
                                                                       Address.id_customer == Customer.id_customer).filter(
            Address.id_address == _id).first()

    def get_by_id(self, _id: int) -> AddressResponseSchema:
        return self.session.query(Address).filter(Address.id_address == _id).first()
    
    def get_by_origin_id(self, origin_id: str) -> Address:
        """Get address by origin ID"""
        return self.session.query(Address).filter(Address.id_origin == origin_id).first()
    
    def get_id_by_id_origin(self, origin_id: int) -> Optional[int]:
        """Get address ID by origin ID (returns only the ID, not the full object)"""
        try:
            result = self.session.query(Address.id_address).filter(Address.id_origin == origin_id).first()
            return result[0] if result else None
        except Exception as e:
            print(f"DEBUG: Error getting address ID by origin {origin_id}: {str(e)}")
            return None

    def bulk_create(self, data_list: list[AddressSchema], batch_size: int = 1000):
        """Bulk insert addresses for better performance"""
        # Get existing origin IDs to avoid duplicates
        origin_ids = [str(data.id_origin) for data in data_list]
        existing_addresses = self.session.query(Address).filter(Address.id_origin.in_(origin_ids)).all()
        existing_origin_ids = {str(address.id_origin) for address in existing_addresses}
        
        # Filter out existing addresses
        new_addresses_data = [data for data in data_list if str(data.id_origin) not in existing_origin_ids]
        
        if not new_addresses_data:
            return 0
        
        # Process in batches
        total_inserted = 0
        for i in range(0, len(new_addresses_data), batch_size):
            batch = new_addresses_data[i:i + batch_size]
            addresses = []
            
            for data in batch:
                address = Address(**data.model_dump())
                addresses.append(address)
            
            self.session.bulk_save_objects(addresses)
            total_inserted += len(addresses)
            
            # Commit every batch
            self.session.commit()
            
        return total_inserted

    def bulk_create_raw_sql(self, data_list: list[AddressSchema], batch_size: int = 5000):
        """
        Ultra-fast bulk create using raw SQL - 10-50x faster than ORM
        For 500k+ records, this is the fastest approach
        """
        if not data_list:
            return 0
        
        from sqlalchemy import text
        from datetime import date
        
        # Get existing addresses by id_origin to avoid duplicates
        origin_ids = [str(data.id_origin) for data in data_list]
        existing_addresses = self.session.query(Address).filter(Address.id_origin.in_(origin_ids)).all()
        existing_origin_ids = {str(address.id_origin) for address in existing_addresses}
        
        # Filter out existing addresses and prepare data
        new_addresses_data = []
        for data in data_list:
            if str(data.id_origin) not in existing_origin_ids:
                # Clean the data
                address_data = data.model_dump()
                if address_data.get('id_country') == 0:
                    address_data['id_country'] = None
                if address_data.get('id_customer') == 0:
                    address_data['id_customer'] = None
                new_addresses_data.append(address_data)
        
        if not new_addresses_data:
            return 0
        
        # Raw SQL insert - much faster than ORM
        insert_sql = text("""
            INSERT INTO addresses (
                id_origin, id_country, id_customer, company, firstname, lastname,
                address1, address2, state, postcode, city, phone, vat, dni, pec, sdi, date_add
            ) VALUES (
                :id_origin, :id_country, :id_customer, :company, :firstname, :lastname,
                :address1, :address2, :state, :postcode, :city, :phone, :vat, :dni, :pec, :sdi, :date_add
            )
        """)
        
        total_inserted = 0
        today = date.today()
        
        # Process in large batches for maximum speed
        for i in range(0, len(new_addresses_data), batch_size):
            batch = new_addresses_data[i:i + batch_size]
            
            # Prepare batch data
            batch_data = []
            for data in batch:
                batch_data.append({
                    'id_origin': data.get('id_origin', 0),
                    'id_country': data.get('id_country'),
                    'id_customer': data.get('id_customer'),
                    'company': data.get('company', ''),
                    'firstname': data.get('firstname', ''),
                    'lastname': data.get('lastname', ''),
                    'address1': data.get('address1', ''),
                    'address2': data.get('address2', ''),
                    'state': data.get('state', ''),
                    'postcode': data.get('postcode', ''),
                    'city': data.get('city', ''),
                    'phone': data.get('phone'),
                    'vat': data.get('vat', ''),
                    'dni': data.get('dni', ''),
                    'pec': data.get('pec', ''),
                    'sdi': data.get('sdi', ''),
                    'date_add': today
                })
            
            # Execute batch insert
            self.session.execute(insert_sql, batch_data)
            self.session.commit()
            total_inserted += len(batch_data)
            
        return total_inserted

    def bulk_create_csv_import(self, data_list: list[AddressSchema], batch_size: int = 10000):
        """
        Ultra-ultra-fast bulk create using CSV import (fastest possible method)
        Only works with MySQL/MariaDB and requires file system access
        """
        if not data_list:
            return 0
        
        import csv
        import tempfile
        import os
        from sqlalchemy import text
        
        # Get existing addresses by id_origin to avoid duplicates
        origin_ids = [str(data.id_origin) for data in data_list]
        existing_addresses = self.session.query(Address).filter(Address.id_origin.in_(origin_ids)).all()
        existing_origin_ids = {str(address.id_origin) for address in existing_addresses}
        
        # Filter out existing addresses and prepare data
        new_addresses_data = []
        for data in data_list:
            if str(data.id_origin) not in existing_origin_ids:
                # Clean the data
                address_data = data.model_dump()
                if address_data.get('id_country') == 0:
                    address_data['id_country'] = None
                if address_data.get('id_customer') == 0:
                    address_data['id_customer'] = None
                new_addresses_data.append(address_data)
        
        if not new_addresses_data:
            return 0
        
        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as csvfile:
            fieldnames = [
                'id_origin', 'id_country', 'id_customer', 'company', 'firstname', 'lastname',
                'address1', 'address2', 'state', 'postcode', 'city', 'phone', 'vat', 'dni', 'pec', 'sdi', 'date_add'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write data in batches
            for i in range(0, len(new_addresses_data), batch_size):
                batch = new_addresses_data[i:i + batch_size]
                for data in batch:
                    writer.writerow({
                        'id_origin': data.get('id_origin', 0),
                        'id_country': data.get('id_country') or '',
                        'id_customer': data.get('id_customer') or '',
                        'company': data.get('company', ''),
                        'firstname': data.get('firstname', ''),
                        'lastname': data.get('lastname', ''),
                        'address1': data.get('address1', ''),
                        'address2': data.get('address2', ''),
                        'state': data.get('state', ''),
                        'postcode': data.get('postcode', ''),
                        'city': data.get('city', ''),
                        'phone': data.get('phone') or '',
                        'vat': data.get('vat', ''),
                        'dni': data.get('dni', ''),
                        'pec': data.get('pec', ''),
                        'sdi': data.get('sdi', ''),
                        'date_add': date.today().strftime('%Y-%m-%d')
                    })
            
            csv_path = csvfile.name
        
        try:
            # Use LOAD DATA INFILE for maximum speed
            load_sql = text(f"""
                LOAD DATA INFILE '{csv_path}'
                INTO TABLE addresses
                FIELDS TERMINATED BY ','
                ENCLOSED BY '"'
                LINES TERMINATED BY '\\n'
                (id_origin, id_country, id_customer, company, firstname, lastname,
                 address1, address2, state, postcode, city, phone, vat, dni, pec, sdi, date_add)
            """)
            
            result = self.session.execute(load_sql)
            self.session.commit()
            
            return len(new_addresses_data)
            
        except Exception as e:
            print(f"CSV import failed, falling back to raw SQL: {str(e)}")
            # Fallback to raw SQL method
            return self.bulk_create_raw_sql(data_list, batch_size)
        finally:
            # Clean up temporary file
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def create(self, data: AddressSchema):
        # Clean the data to handle None values properly
        address_data = data.model_dump()
        
        # Convert 0 to None for foreign key fields
        if address_data.get('id_country') == 0:
            address_data['id_country'] = None
        if address_data.get('id_customer') == 0:
            address_data['id_customer'] = None
            
        address = Address(**address_data)
        address.date_add = date.today()

        self.session.add(address)
        self.session.commit()
        self.session.refresh(address)
        return address.id_address

    def create_and_get_id(self, data: AddressSchema):
        # Clean the data to handle None values properly
        address_data = data.model_dump()
        
        # Convert 0 to None for foreign key fields
        if address_data.get('id_country') == 0:
            address_data['id_country'] = None
        if address_data.get('id_customer') == 0:
            address_data['id_customer'] = None
            
        address = Address(**address_data)
        address.date_add = date.today()

        self.session.add(address)
        self.session.commit()
        self.session.refresh(address)
        return address.id_address

    def get_or_create_address(self, address_data: AddressSchema, customer_id: int) -> int:
        existing_address = self.get_by_address(
            city=address_data.city,
            country=address_data.id_country,
            address=address_data.address1,
            postcode=address_data.postcode,
            firstname=address_data.firstname,
            lastname=address_data.lastname
        )
        if existing_address:
            return existing_address.id_address
        else:
            address_data.id_customer = customer_id
            return self.create_and_get_id(address_data)

    def update(self, edited_address: Address, data: AddressSchema):

        entity_updated = data.model_dump(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_address, key) and value is not None:
                setattr(edited_address, key, value)

        self.session.add(edited_address)
        self.session.commit()

    def delete(self, address: Address) -> bool:
        self.session.delete(address)
        self.session.commit()

        return True

    @staticmethod
    def formatted_output(address: Address,
                         country: Country,
                         customer: Customer):

        return {
            "id_address": address.id_address,
            "id_origin": address.id_origin,
            "customer": customer if customer else None,
            "country": country if country else None,
            "company": address.company,
            "firstname": address.firstname,
            "lastname": address.lastname,
            "address1": address.address1,
            "address2": address.address2,
            "state": address.state,
            "postcode": address.postcode,
            "city": address.city,
            "phone": address.phone,
            "mobile_phone": address.mobile_phone,
            "vat": address.vat,
            "dni": address.dni,
            "pec": address.pec,
            "sdi": address.sdi,
            "date_add": address.date_add.strftime('%d-%m-%Y')
        }
