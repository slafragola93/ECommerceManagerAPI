from sqlalchemy import func, desc, and_
from sqlalchemy.orm import Session
from ..models.app_configuration import AppConfiguration
from src.schemas.app_configuration_schema import *
from src.services import QueryUtils


class AppConfigurationRepository:
    """Repository per le configurazioni dell'applicazione"""

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self, page: int = 1, limit: int = 10) -> list[AppConfiguration]:
        """
        Recupera tutte le configurazioni dell'app

        Args:
            page (int): Numero di pagina
            limit (int): Limite di risultati per pagina

        Returns:
            list[AppConfiguration]: Lista delle configurazioni
        """
        return self.session.query(AppConfiguration).order_by(
            desc(AppConfiguration.category), 
            AppConfiguration.name
        ).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self) -> int:
        """
        Conta il numero totale di configurazioni

        Returns:
            int: Numero totale di configurazioni
        """
        return self.session.query(func.count(AppConfiguration.id_app_configuration)).scalar()

    def get_by_id(self, _id: int) -> AppConfiguration:
        """
        Ottieni configurazione per ID

        Args:
            _id (int): ID della configurazione

        Returns:
            AppConfiguration: Istanza configurazione
        """
        return self.session.query(AppConfiguration).filter(
            AppConfiguration.id_app_configuration == _id
        ).first()

    def get_by_category(self, category: str) -> list[AppConfiguration]:
        """
        Recupera tutte le configurazioni di una categoria specifica

        Args:
            category (str): Nome della categoria

        Returns:
            list[AppConfiguration]: Lista delle configurazioni della categoria
        """
        return self.session.query(AppConfiguration).filter(
            AppConfiguration.category == category
        ).order_by(AppConfiguration.name).all()

    def get_by_name_and_category(self, name: str, category: str) -> AppConfiguration:
        """
        Recupera una configurazione specifica per nome e categoria

        Args:
            name (str): Nome della configurazione
            category (str): Categoria della configurazione

        Returns:
            AppConfiguration: Configurazione trovata
        """
        return self.session.query(AppConfiguration).filter(
            and_(
                AppConfiguration.name == name,
                AppConfiguration.category == category
            )
        ).first()

    def get_all_categories(self) -> list[str]:
        """
        Recupera tutte le categorie disponibili

        Returns:
            list[str]: Lista delle categorie
        """
        result = self.session.query(AppConfiguration.category).distinct().all()
        return [row[0] for row in result]

    def get_configurations_by_category(self) -> dict[str, list[AppConfiguration]]:
        """
        Recupera tutte le configurazioni raggruppate per categoria

        Returns:
            dict[str, list[AppConfiguration]]: Dizionario con categorie come chiavi
        """
        configurations = self.session.query(AppConfiguration).order_by(
            AppConfiguration.category, 
            AppConfiguration.name
        ).all()
        
        result = {}
        for config in configurations:
            if config.category not in result:
                result[config.category] = []
            result[config.category].append(config)
        
        return result

    def create(self, data: AppConfigurationSchema) -> AppConfiguration:
        """
        Crea una nuova configurazione

        Args:
            data (AppConfigurationSchema): Dati della configurazione

        Returns:
            AppConfiguration: Configurazione creata
        """
        configuration = AppConfiguration(**data.model_dump())
        self.session.add(configuration)
        self.session.commit()
        self.session.refresh(configuration)
        return configuration

    def create_bulk(self, configurations_data: list[AppConfigurationSchema]) -> list[AppConfiguration]:
        """
        Crea multiple configurazioni in batch

        Args:
            configurations_data (list[AppConfigurationSchema]): Lista dei dati delle configurazioni

        Returns:
            list[AppConfiguration]: Lista delle configurazioni create
        """
        configurations = []
        for data in configurations_data:
            configuration = AppConfiguration(**data.model_dump())
            configurations.append(configuration)
            self.session.add(configuration)
        
        self.session.commit()
        
        # Refresh tutte le configurazioni
        for config in configurations:
            self.session.refresh(config)
        
        return configurations

    def update(self, edited_configuration: AppConfiguration, data: AppConfigurationUpdateSchema) -> AppConfiguration:
        """
        Aggiorna una configurazione esistente

        Args:
            edited_configuration (AppConfiguration): Configurazione da aggiornare
            data (AppConfigurationUpdateSchema): Nuovi dati

        Returns:
            AppConfiguration: Configurazione aggiornata
        """
        entity_updated = data.model_dump(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_configuration, key) and value is not None:
                setattr(edited_configuration, key, value)

        self.session.add(edited_configuration)
        self.session.commit()
        self.session.refresh(edited_configuration)
        return edited_configuration

    def update_by_name_and_category(self, name: str, category: str, value: str) -> AppConfiguration:
        """
        Aggiorna il valore di una configurazione specifica

        Args:
            name (str): Nome della configurazione
            category (str): Categoria della configurazione
            value (str): Nuovo valore

        Returns:
            AppConfiguration: Configurazione aggiornata
        """
        configuration = self.get_by_name_and_category(name, category)
        if configuration:
            configuration.value = value
            self.session.add(configuration)
            self.session.commit()
            self.session.refresh(configuration)
        return configuration

    def delete(self, configuration: AppConfiguration) -> bool:
        """
        Elimina una configurazione

        Args:
            configuration (AppConfiguration): Configurazione da eliminare

        Returns:
            bool: True se eliminata con successo
        """
        self.session.delete(configuration)
        self.session.commit()
        return True

    def delete_by_name_and_category(self, name: str, category: str) -> bool:
        """
        Elimina una configurazione per nome e categoria

        Args:
            name (str): Nome della configurazione
            category (str): Categoria della configurazione

        Returns:
            bool: True se eliminata con successo
        """
        configuration = self.get_by_name_and_category(name, category)
        if configuration:
            return self.delete(configuration)
        return False

    def get_configuration_value(self, name: str, category: str, default_value: str = None) -> str:
        """
        Recupera il valore di una configurazione specifica

        Args:
            name (str): Nome della configurazione
            category (str): Categoria della configurazione
            default_value (str): Valore di default se non trovato

        Returns:
            str: Valore della configurazione o default
        """
        configuration = self.get_by_name_and_category(name, category)
        return configuration.value if configuration else default_value
