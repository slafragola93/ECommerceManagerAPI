from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models import Tax
from src.schemas.tax_schema import *
from src.services import QueryUtils


class TaxRepository:
    """
    Repository clienti
    """

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self,
                page: int = 1, limit: int = 10
                ) -> AllTaxesResponseSchema:

        return self.session.query(Tax).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self) -> int:
        return self.session.query(func.count(Tax.id_tax)).scalar()

    def get_by_id(self, _id: int) -> TaxResponseSchema:
        return self.session.query(Tax).filter(Tax.id_tax == _id).first()

    def create(self, data: TaxSchema):
        tax = Tax(**data.model_dump())

        self.session.add(tax)
        self.session.commit()
        self.session.refresh(tax)

    def update(self, edited_tax: Tax, data: TaxSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_tax, key) and value is not None:
                setattr(edited_tax, key, value)

        self.session.add(edited_tax)
        self.session.commit()

    def delete(self, tax: Tax) -> bool:
        self.session.delete(tax)
        self.session.commit()

        return True

    def define_tax(self, id_country: int) -> int:
        # Se Italia ritorna quella default
        if id_country == 10:
            tax = self.session.query(Tax).filter(Tax.is_default == True).first()
            return tax.id_tax if tax else 1  # Fallback a ID 1 se non trovato
        else:
            tax = self.session.query(Tax).filter(Tax.id_country == id_country).first()
            return tax.id_tax if tax else 1  # Fallback a ID 1 se non trovato

    def get_by_id_country(self, id_country: int) -> list[Tax]:
        """
        Recupera tutte le tasse per un paese specifico
        
        Args:
            id_country (int): ID del paese
            
        Returns:
            list[Tax]: Lista delle tasse per il paese
        """
        return self.session.query(Tax).filter(Tax.id_country == id_country).all()
    
    def get_default_tax_rate(self) -> int:
        """
        Recupera la percentuale IVA di default

        Returns:
            int: La percentuale IVA di default
        """
        return self.session.query(Tax.percentage).filter(Tax.is_default == 1).first()

    def get_percentage_by_id(self, id_tax: int) -> int:
        """
        Recupera la percentuale IVA per un ID tax specifico
        
        Args:
            id_tax (int): ID della tassa
            
        Returns:
            int: Percentuale IVA (es. 22 per 22%), 0 se non trovato
        """
        tax = self.session.query(Tax).filter(Tax.id_tax == id_tax).first()
        return tax.percentage if tax and tax.percentage else 0