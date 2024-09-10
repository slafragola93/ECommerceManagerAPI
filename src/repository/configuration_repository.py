from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from ..models import Configuration
from src.schemas.configuration_schema import *
from src.services import QueryUtils


class ConfigurationRepository:
    """Repository configuration"""

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self, page: int = 1, limit: int = 10) -> AllConfigurationsResponseSchema:
        """
        Recupera tutte le configurazioni

        Returns:
            AllConfigurationsResponseSchema: Tutti le configurazioni
        """

        return self.session.query(Configuration).order_by(desc(Configuration.id_configuration)).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self) -> int:
        return self.session.query(func.count(Configuration.id_configuration)).scalar()

    def get_by_id(self, _id: int) -> ConfigurationResponseSchema:
        """
        Ottieni brand per ID

        Args:
            _id (int):  ID Configuration.

        Returns:
            ConfigurationResponseSchema: Istanza configurazione
        """
        return self.session.query(Configuration).filter(Configuration.id_configuration == _id).first()

    def create(self, data: ConfigurationSchema):

        configuration = Configuration(**data.model_dump())

        self.session.add(configuration)
        self.session.commit()
        self.session.refresh(configuration)

    def update(self,
               edited_configuration: Configuration,
               data: ConfigurationSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_configuration, key) and value is not None:
                setattr(edited_configuration, key, value)

        self.session.add(edited_configuration)
        self.session.commit()

    def delete(self, configuration: Configuration) -> bool:
        self.session.delete(configuration)
        self.session.commit()

        return True
