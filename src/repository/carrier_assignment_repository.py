from fastapi import HTTPException
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from typing import Optional, List
from ..models import CarrierAssignment, CarrierApi
from src.schemas.carrier_assignment_schema import *
from src.services import QueryUtils


class CarrierAssignmentRepository:
    """Repository per le assegnazioni automatiche dei corrieri"""

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self, 
                carrier_assignments_ids: Optional[str] = None,
                carrier_apis_ids: Optional[str] = None,
                page: int = 1, 
                limit: int = 10) -> List[CarrierAssignment]:
        """
        Recupera tutte le assegnazioni di corrieri con filtri opzionali

        Args:
            carrier_assignments_ids: ID delle assegnazioni, separati da virgole
            carrier_apis_ids: ID dei carrier API, separati da virgole
            page: Pagina corrente per la paginazione
            limit: Numero di record per pagina

        Returns:
            List[CarrierAssignment]: Lista delle assegnazioni
        """
        query = self.session.query(CarrierAssignment).order_by(desc(CarrierAssignment.id_carrier_assignment))
        
        try:
            # Filtri per ID
            if carrier_assignments_ids:
                query = QueryUtils.filter_by_id(query, CarrierAssignment, 'id_carrier_assignment', carrier_assignments_ids)
            if carrier_apis_ids:
                query = QueryUtils.filter_by_id(query, CarrierAssignment, 'id_carrier_api', carrier_apis_ids)
                
        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")
        
        return query.offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self,
                  carrier_assignments_ids: Optional[str] = None,
                  carrier_apis_ids: Optional[str] = None) -> int:
        """
        Conta il numero totale di assegnazioni con i filtri applicati

        Args:
            carrier_assignments_ids: ID delle assegnazioni, separati da virgole
            carrier_apis_ids: ID dei carrier API, separati da virgole

        Returns:
            int: Numero totale di assegnazioni
        """
        query = self.session.query(func.count(CarrierAssignment.id_carrier_assignment))
        
        try:
            # Applica gli stessi filtri di get_all
            if carrier_assignments_ids:
                query = QueryUtils.filter_by_id(query, CarrierAssignment, 'id_carrier_assignment', carrier_assignments_ids)
            if carrier_apis_ids:
                query = QueryUtils.filter_by_id(query, CarrierAssignment, 'id_carrier_api', carrier_apis_ids)
                
        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")
        
        return query.scalar()

    def get_by_id(self, _id: int) -> Optional[CarrierAssignment]:
        """
        Recupera un'assegnazione per ID

        Args:
            _id (int): ID dell'assegnazione

        Returns:
            Optional[CarrierAssignment]: L'assegnazione se trovata, None altrimenti
        """
        return self.session.query(CarrierAssignment).filter(CarrierAssignment.id_carrier_assignment == _id).first()

    def create(self, data: CarrierAssignmentSchema) -> int:
        """
        Crea una nuova assegnazione di corriere

        Args:
            data (CarrierAssignmentSchema): Dati dell'assegnazione

        Returns:
            int: ID dell'assegnazione creata
        """
        assignment = CarrierAssignment(**data.model_dump())
        
        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)
        
        return assignment.id_carrier_assignment

    def update(self, edited_assignment: CarrierAssignment, data: CarrierAssignmentUpdateSchema):
        """
        Aggiorna un'assegnazione esistente

        Args:
            edited_assignment (CarrierAssignment): Assegnazione da aggiornare
            data (CarrierAssignmentUpdateSchema): Nuovi dati
        """
        entity_updated = data.model_dump(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_assignment, key) and value is not None:
                setattr(edited_assignment, key, value)

        self.session.add(edited_assignment)
        self.session.commit()

    def delete(self, assignment: CarrierAssignment) -> bool:
        """
        Elimina un'assegnazione

        Args:
            assignment (CarrierAssignment): Assegnazione da eliminare

        Returns:
            bool: True se eliminata con successo
        """
        self.session.delete(assignment)
        self.session.commit()
        return True

    def formatted_output(self, assignment: CarrierAssignment) -> dict:
        """
        Formatta l'output di un'assegnazione con le relazioni popolate

        Args:
            assignment (CarrierAssignment): Assegnazione da formattare

        Returns:
            dict: Assegnazione formattata
        """
        # Helper per formattare il carrier API
        def format_carrier_api(carrier_api_id):
            if not carrier_api_id:
                return None
            carrier_api = self.session.query(CarrierApi).filter(CarrierApi.id_carrier_api == carrier_api_id).first()
            if not carrier_api:
                return None
            return {
                "id_carrier_api": carrier_api.id_carrier_api,
                "name": carrier_api.name,
                "account_number": carrier_api.account_number,
                "site_id": carrier_api.site_id,
                "national_service": carrier_api.national_service,
                "international_service": carrier_api.international_service,
                "is_active": carrier_api.is_active
            }

        return {
            "id_carrier_assignment": assignment.id_carrier_assignment,
            "id_carrier_api": assignment.id_carrier_api,
            "postal_codes": assignment.postal_codes,
            "countries": assignment.countries,
            "origin_carriers": assignment.origin_carriers,
            "min_weight": assignment.min_weight,
            "max_weight": assignment.max_weight,
            "carrier_api": format_carrier_api(assignment.id_carrier_api)
        }

    def find_matching_assignment(self, 
                                postal_code: Optional[str] = None,
                                country_id: Optional[int] = None,
                                origin_carrier_id: Optional[int] = None,
                                weight: Optional[float] = None) -> Optional[CarrierAssignment]:
        """
        Trova l'assegnazione che corrisponde ai criteri specificati

        Args:
            postal_code: Codice postale
            country_id: ID del paese
            origin_carrier_id: ID del corriere di origine
            weight: Peso del pacco

        Returns:
            Optional[CarrierAssignment]: Prima assegnazione che corrisponde ai criteri
        """
        query = self.session.query(CarrierAssignment)
        
        # Filtro per peso se specificato
        if weight is not None:
            query = query.filter(
                (CarrierAssignment.min_weight.is_(None)) | (CarrierAssignment.min_weight <= weight),
                (CarrierAssignment.max_weight.is_(None)) | (CarrierAssignment.max_weight >= weight)
            )
        
        # Filtro per codice postale se specificato
        if postal_code:
            query = query.filter(
                (CarrierAssignment.postal_codes.is_(None)) | 
                (CarrierAssignment.postal_codes.like(f'%{postal_code}%'))
            )
        
        # Filtro per paese se specificato
        if country_id:
            query = query.filter(
                (CarrierAssignment.countries.is_(None)) | 
                (CarrierAssignment.countries.like(f'%{country_id}%'))
            )
        
        # Filtro per corriere di origine se specificato
        if origin_carrier_id:
            query = query.filter(
                (CarrierAssignment.origin_carriers.is_(None)) | 
                (CarrierAssignment.origin_carriers.like(f'%{origin_carrier_id}%'))
            )
        
        # Ordina per priorità: regole con più condizioni specifiche hanno priorità
        # Calcola un punteggio di specificità per ogni regola
        from sqlalchemy import case, func
        
        specificity_score = (
            case((CarrierAssignment.postal_codes.isnot(None), 1), else_=0) +
            case((CarrierAssignment.countries.isnot(None), 1), else_=0) +
            case((CarrierAssignment.origin_carriers.isnot(None), 1), else_=0) +
            case((CarrierAssignment.min_weight.isnot(None), 1), else_=0) +
            case((CarrierAssignment.max_weight.isnot(None), 1), else_=0)
        )
        
        return query.order_by(specificity_score.desc(), CarrierAssignment.id_carrier_assignment).first()
