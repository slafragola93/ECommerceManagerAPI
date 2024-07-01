from datetime import date
from fastapi import HTTPException
from sqlalchemy import func
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
        ).join(Country, Address.id_country == Country.id_country).join(Customer,
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
        ).join(Country, Address.id_country == Country.id_country).join(Customer,
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
        ).join(Country, Address.id_country == Country.id_country).join(Customer,
                                                                       Address.id_customer == Customer.id_customer).filter(
            Address.id_address == _id).first()

    def get_by_id(self, _id: int) -> AddressResponseSchema:
        return self.session.query(Address).filter(Address.id_address == _id).first()

    def create(self, data: AddressSchema):
        address = Address(**data.model_dump(exclude=['customer']))

        if isinstance(data.customer, CustomerSchema):
            cr = CustomerRepository(self.session)
            customer = cr.get_by_email(data.customer.email)

            id_customer = cr.create_and_get_id(data.customer) if customer is None else customer.id_customer

        else:
            id_customer = data.customer

        address.id_customer = id_customer
        address.date_add = date.today()

        self.session.add(address)
        self.session.commit()
        self.session.refresh(address)

    def create_and_get_id(self, data: AddressSchema):
        address = Address(**data.model_dump(exclude=["customer"]))
        address.date_add = date.today()

        if isinstance(data.customer, CustomerSchema):
            cr = CustomerRepository(self.session)
            customer = cr.get_by_email(data.customer.email)

            id_customer = cr.create_and_get_id(data.customer) if customer is None else customer.id_customer

        else:
            id_customer = data.customer

        address.id_customer = id_customer

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
            address_data.customer = customer_id
            return self.create_and_get_id(address_data)

    def update(self, edited_address: Address, data: AddressSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

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
            "customer": {
                "id_customer": customer.id_customer if customer else 0,
                "id_origin": customer.id_origin if customer else None,
                "id_lang": customer.id_lang if customer else 0,
                "firstname": customer.firstname if customer else None,
                "lastname": customer.lastname if customer else None,
                "email": customer.email if customer else None,
                "date_add": customer.date_add.isoformat() if customer else None
            },
            "country": {
                "id_country": country.id_country if country else None,
                "name": country.name if country else None,
                "iso_code": country.iso_code if country else None,
            },
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
