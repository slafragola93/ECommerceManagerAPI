"""
Entity Mapper for CSV Import System.

Maps CSV rows to Pydantic schemas with type conversion and field transformation.
Follows Single Responsibility and Open/Closed principles.
"""
from __future__ import annotations

from typing import Dict, Any, Type, Optional, List
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.schemas.product_schema import ProductSchema
from src.schemas.customer_schema import CustomerSchema
from src.schemas.address_schema import AddressSchema
from src.schemas.brand_schema import BrandSchema
from src.schemas.category_schema import CategorySchema
from src.schemas.carrier_schema import CarrierSchema
from src.schemas.country_schema import CountrySchema
from src.schemas.lang_schema import LangSchema
from src.schemas.payment_schema import PaymentSchema
from src.schemas.order_schema import OrderSchema
from src.schemas.order_detail_schema import OrderDetailSchema


class EntityMapper:
    """
    Mapper CSV → Pydantic Schema con gestione id_platform.
    
    Stateless mapper - configurazione dichiarativa.
    """
    
    # Mapping entity_type → Schema Pydantic
    SCHEMA_MAPPING: Dict[str, Type[BaseModel]] = {
        'products': ProductSchema,
        'customers': CustomerSchema,
        'addresses': AddressSchema,
        'brands': BrandSchema,
        'categories': CategorySchema,
        'carriers': CarrierSchema,
        'countries': CountrySchema,
        'languages': LangSchema,
        'payments': PaymentSchema,
        'orders': OrderSchema,
        'order_details': OrderDetailSchema
    }
    
    # Entità che hanno campo id_platform
    PLATFORM_AWARE_ENTITIES = {'products', 'addresses', 'orders'}
    
    # Campi richiesti per entità (per validazione headers)
    REQUIRED_FIELDS: Dict[str, List[str]] = {
        'products': ['id_origin', 'name', 'sku'],
        'customers': ['id_origin', 'firstname', 'lastname', 'email', 'id_lang'],
        'addresses': ['id_origin', 'id_customer', 'firstname', 'lastname', 'address1', 'city', 'postcode', 'state', 'phone'],
        'brands': ['id_origin', 'name'],
        'categories': ['id_origin', 'name'],
        'carriers': ['id_origin', 'name'],
        'countries': ['id_origin', 'name', 'iso_code'],
        'languages': ['id_origin', 'name', 'iso_code'],
        'payments': ['name'],
        'orders': ['id_origin', 'id_customer', 'id_address_delivery', 'id_address_invoice'],
        'order_details': ['id_order', 'id_origin', 'id_platform', 'product_name', 'product_qty', 'product_price', 'product_weight', 'tax_percentage']
    }
    
    # Campi con default se non forniti
    DEFAULT_VALUES: Dict[str, Dict[str, Any]] = {
        'products': {
            'reference': 'ND',
            'type': '',
            'weight': 0.0,
            'depth': 0.0,
            'height': 0.0,
            'width': 0.0,
            'price_without_tax': 0.0,
            'quantity': 0,
            'id_category': 0,
            'id_brand': 0
        },
        'addresses': {
            'address2': '',
            'company': '',
            'mobile_phone': None,
            'vat': '',
            'dni': '',
            'pec': '',
            'sdi': '',
            'ipa': ''
        },
        'carriers': {
            'tracking_url': '',
            'is_active': True
        }
    }
    
    @staticmethod
    def get_schema(entity_type: str) -> Type[BaseModel]:
        """Ottiene schema Pydantic per entity type"""
        schema = EntityMapper.SCHEMA_MAPPING.get(entity_type)
        if not schema:
            raise ValueError(f"Unknown entity type: {entity_type}")
        return schema
    
    @staticmethod
    def get_required_fields(entity_type: str) -> List[str]:
        """Ottiene lista campi richiesti per entity type"""
        return EntityMapper.REQUIRED_FIELDS.get(entity_type, [])
    
    @staticmethod
    def map_to_schema(
        row: Dict[str, Any],
        entity_type: str,
        id_platform: int = 1,
        db: Optional[Session] = None
    ) -> BaseModel:
        """
        Map CSV row to Pydantic schema instance.
        
        Args:
            row: Riga CSV come dizionario
            entity_type: Tipo entità
            id_platform: ID platform (viene iniettato se entity è platform-aware)
            db: Database session per lookup (necessario per order_details)
            
        Returns:
            Istanza schema Pydantic validato
            
        Raises:
            ValueError: Se entity_type sconosciuto
            ValidationError: Se Pydantic validation fallisce
        """
        schema_class = EntityMapper.get_schema(entity_type)
        
        # Transform fields
        transformed = EntityMapper.transform_fields(row, entity_type, id_platform, db)
        
        # Create and validate schema
        return schema_class(**transformed)
    
    @staticmethod
    def transform_fields(
        row: Dict[str, Any],
        entity_type: str,
        id_platform: int = 1,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Transform and clean CSV row fields.
        
        - Converte tipi (str → int/float/bool)
        - Aggiunge defaults
        - Inietta id_platform se necessario
        - Rimuove campi extra (es. _row_number)
        - Per order_details: converte id_origin->id_product e Tax->id_tax
        
        Args:
            row: Riga CSV raw
            entity_type: Tipo entità
            id_platform: ID platform
            db: Database session per lookup (necessario per order_details)
            
        Returns:
            Dizionario pulito per schema
        """
        # Rimuovi metadati interni
        cleaned = {k: v for k, v in row.items() if not k.startswith('_')}
        
        # Converti empty strings a None per campi opzionali
        for key, value in cleaned.items():
            if value == '':
                cleaned[key] = None
        
        # Inietta id_platform se entity è platform-aware
        if entity_type in EntityMapper.PLATFORM_AWARE_ENTITIES:
            cleaned['id_platform'] = id_platform
        
        # Per order_details: gestisci id_platform, id_origin->id_product e Tax->id_tax
        if entity_type == 'order_details':
            # Inietta id_platform se presente nel CSV, altrimenti usa quello passato come parametro
            if 'id_platform' in cleaned and cleaned['id_platform'] is not None:
                # Usa id_platform dal CSV
                pass
            else:
                # Usa id_platform dal parametro
                cleaned['id_platform'] = id_platform
            
            # Converti id_origin (prodotto) in id_product
            if 'id_origin' in cleaned and cleaned['id_origin'] is not None and db is not None:
                from src.models.product import Product
                from sqlalchemy.orm import load_only
                product_origin = int(cleaned['id_origin'])
                product = db.query(Product).options(
                    load_only(Product.id_product)
                ).filter(
                    Product.id_origin == product_origin,
                    Product.id_platform == cleaned.get('id_platform', id_platform)
                ).first()
                if product:
                    cleaned['id_product'] = product.id_product
                else:
                    raise ValueError(f"Prodotto con id_origin={product_origin} e id_platform={cleaned.get('id_platform', id_platform)} non trovato")
                # Rimuovi id_origin dal dizionario (non fa parte dello schema OrderDetailSchema)
                cleaned.pop('id_origin', None)
            
            # Converti tax_percentage (percentuale) in id_tax
            if 'tax_percentage' in cleaned and cleaned['tax_percentage'] is not None and db is not None:
                from src.models.tax import Tax
                from sqlalchemy.orm import load_only
                tax_percentage = float(cleaned['tax_percentage'])
                # Cerca la tassa con questa percentuale (query idratata)
                tax = db.query(Tax).options(
                    load_only(Tax.id_tax)
                ).filter(Tax.percentage == tax_percentage).first()
                if tax:
                    cleaned['id_tax'] = tax.id_tax
                else:
                    raise ValueError(f"Tax con percentuale {tax_percentage} non trovata")
                # Rimuovi il campo 'tax_percentage' dal dizionario
                cleaned.pop('tax_percentage', None)
        
          # Applica defaults
        defaults = EntityMapper.DEFAULT_VALUES.get(entity_type, {})
        for key, default_value in defaults.items():
            if key not in cleaned or cleaned[key] is None:
                cleaned[key] = default_value
        
        # Type conversions specifiche per entità
        cleaned = EntityMapper._apply_type_conversions(cleaned, entity_type)
        
        return cleaned
    
    @staticmethod
    def _apply_type_conversions(data: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
        """
        Applica conversioni tipo specifiche per entity.
        
        Args:
            data: Dati da convertire
            entity_type: Tipo entità
            
        Returns:
            Dati con tipi convertiti
        """
        # Conversioni comuni per tutti
        int_fields = ['id_origin', 'id_customer', 'id_country', 'id_category', 'id_brand', 
                      'id_lang', 'id_product', 'id_order', 'id_tax', 'id_payment',
                      'id_address_delivery', 'id_address_invoice', 'id_carrier',
                      'id_shipping', 'id_sectional', 'id_order_state', 'product_qty', 'quantity',
                      'id_platform']
        
        float_fields = ['weight', 'depth', 'height', 'width', 'price_without_tax',
                       'purchase_price', 'product_price', 'product_weight',
                       'unit_price_tax_incl', 'unit_price_tax_excl',
                       'reduction_percent', 'reduction_amount',
                       'total_price_tax_excl', 'total_paid', 'total_discounts', 'total_weight',
                       'price_tax_incl', 'price_tax_excl', 'tax_percentage']
        
        bool_fields = ['is_active', 'is_default', 'is_invoice_requested', 'is_payed']
        
        for key, value in data.items():
            if value is None or value == '':
                continue
            
            try:
                if key in int_fields:
                    data[key] = int(float(value)) if value else 0
                elif key in float_fields:
                    data[key] = float(value) if value else 0.0
                elif key in bool_fields:
                    if isinstance(value, str):
                        data[key] = value.lower() in ('true', '1', 'yes', 'si', 'y')
                    else:
                        data[key] = bool(value)
            except (ValueError, TypeError):
                # Mantieni valore originale, la validazione Pydantic segnalerà l'errore
                pass
        
        return data
    
    @staticmethod
    def generate_csv_template(entity_type: str) -> str:
        """
        Genera template CSV con headers per entity type.
        
        Args:
            entity_type: Tipo entità
            
        Returns:
            Stringa CSV con headers (senza id_platform)
        """
        required_fields = EntityMapper.get_required_fields(entity_type)
        defaults = EntityMapper.DEFAULT_VALUES.get(entity_type, {})
        
        # Combina required + optional (da defaults)
        all_fields = list(required_fields) + [k for k in defaults.keys() if k not in required_fields]
        
        # Rimuovi id_platform dal template (viene passato come query param)
        all_fields = [f for f in all_fields if f != 'id_platform']
        
        return ','.join(all_fields) + '\n'

