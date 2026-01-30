"""
Fixture principali per i test di ECommerceManagerAPI
"""
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator, Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Aggiungi il path del progetto
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.main import app
from src.database import Base, get_db
from src.services.routers.auth_service import get_current_user
from src.events.runtime import set_event_bus
from src.events.core.event_bus import EventBus
from src.events.core.event import Event
from src.factories.services.carrier_service_factory import CarrierServiceFactory
from src.services.interfaces.shipment_service_interface import IShipmentService
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository


# ============================================================================
# Database Test Setup
# ============================================================================

# SQLite in-memory per i test
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Crea una sessione database isolata per ogni test.
    Rollback automatico a fine test.
    """
    # Crea le tabelle
    Base.metadata.create_all(bind=test_engine)
    
    # Crea sessione
    session = TestSessionLocal()
    
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        # Pulisci le tabelle
        Base.metadata.drop_all(bind=test_engine)


def override_get_db():
    """Override per get_db dependency"""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# EventBus Spy
# ============================================================================

class EventBusSpy(EventBus):
    """EventBus che registra tutti gli eventi pubblicati per i test"""
    
    def __init__(self):
        super().__init__()
        self.published_events: List[Event] = []
    
    async def publish(self, event: Event) -> None:
        """Override per registrare l'evento prima di pubblicarlo"""
        self.published_events.append(event)
        await super().publish(event)
    
    def clear(self):
        """Pulisce la lista degli eventi pubblicati"""
        self.published_events.clear()
    
    def get_events_by_type(self, event_type: str) -> List[Event]:
        """Ritorna tutti gli eventi di un tipo specifico"""
        return [e for e in self.published_events if e.event_type == event_type]


@pytest.fixture(scope="function")
def event_bus_spy() -> EventBusSpy:
    """Fixture per EventBus spy"""
    spy = EventBusSpy()
    set_event_bus(spy)
    yield spy
    # Reset dopo il test
    set_event_bus(None)


# ============================================================================
# Fake Carrier Service
# ============================================================================

class FakeShipmentService(IShipmentService):
    """Fake shipment service per i test"""
    
    def __init__(self, awb: str = "TEST123456789"):
        self.awb = awb
        self.created_shipments: List[int] = []
        self.cancelled_shipments: List[int] = []
    
    async def create_shipment(self, order_id: int, id_shipping: Optional[int] = None) -> Dict[str, Any]:
        """Crea una spedizione fake"""
        self.created_shipments.append(order_id)
        return {
            "awb": self.awb,
            "tracking": self.awb,
            "order_id": order_id,
            "id_shipping": id_shipping,
            "status": "created"
        }
    
    async def get_label_file_path(self, awb: str) -> Optional[str]:
        """Ritorna un path fake per l'etichetta"""
        return f"/media/shipments/{awb}.pdf"
    
    async def cancel_shipment(self, order_id: int) -> Dict[str, Any]:
        """Cancella una spedizione fake"""
        self.cancelled_shipments.append(order_id)
        return {
            "order_id": order_id,
            "status": "cancelled"
        }


class FakeCarrierServiceFactory(CarrierServiceFactory):
    """Factory fake che ritorna FakeShipmentService"""
    
    def __init__(self, carrier_repository: IApiCarrierRepository, awb: str = "TEST123456789"):
        super().__init__(carrier_repository)
        self.fake_service = FakeShipmentService(awb=awb)
    
    def get_shipment_service(self, id_carrier_api: int, db: Session) -> IShipmentService:
        """Ritorna sempre il fake service"""
        return self.fake_service


# ============================================================================
# Auth Override
# ============================================================================

def create_test_user(
    username: str = "testuser",
    user_id: int = 1,
    roles: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Crea un dict utente per i test"""
    if roles is None:
        roles = [{"name": "USER", "permissions": ["R"]}]
    
    return {
        "username": username,
        "id": user_id,
        "roles": roles
    }


def override_get_current_user(user: Dict[str, Any] = None):
    """Override per get_current_user dependency"""
    if user is None:
        user = create_test_user()
    
    async def _get_current_user():
        return user
    
    return _get_current_user


# ============================================================================
# App Fixture con Overrides
# ============================================================================

@pytest.fixture(scope="function")
def test_app(db_session: Session, event_bus_spy: EventBusSpy):
    """
    Crea l'app FastAPI con dependency overrides per i test.
    """
    # Override database
    app.dependency_overrides[get_db] = override_get_db
    
    # Override auth (default user)
    default_user = create_test_user()
    app.dependency_overrides[get_current_user] = lambda: default_user
    
    # Disabilita background tasks
    with patch.dict(os.environ, {"TRACKING_POLLING_ENABLED": "false"}):
        # Override cache per usare solo memory
        with patch('src.core.settings.get_cache_settings') as mock_cache:
            mock_settings = MagicMock()
            mock_settings.cache_backend = "memory"
            mock_settings.cache_enabled = True
            mock_cache.return_value = mock_settings
            
            try:
                yield app
            finally:
                # Cleanup
                app.dependency_overrides.clear()


# ============================================================================
# HTTP Clients
# ============================================================================

@pytest_asyncio.fixture
def client(test_app) -> TestClient:
    """Client HTTP sincrono per test semplici"""
    return TestClient(test_app)


@pytest_asyncio.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Client HTTP asincrono"""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        yield ac


# ============================================================================
# Client con Ruoli Predefiniti
# ============================================================================

@pytest.fixture
def admin_user() -> Dict[str, Any]:
    """Utente admin per i test"""
    return create_test_user(
        username="admin",
        user_id=1,
        roles=[{"name": "ADMIN", "permissions": ["C", "R", "U", "D"]}]
    )


@pytest.fixture
def ordini_user() -> Dict[str, Any]:
    """Utente con ruolo ORDINI per i test"""
    return create_test_user(
        username="ordini_user",
        user_id=2,
        roles=[{"name": "ORDINI", "permissions": ["C", "R", "U", "D"]}]
    )


@pytest.fixture
def user_user() -> Dict[str, Any]:
    """Utente base per i test"""
    return create_test_user(
        username="user",
        user_id=3,
        roles=[{"name": "USER", "permissions": ["R"]}]
    )


@pytest.fixture
def admin_client(test_app, admin_user) -> TestClient:
    """Client con utente admin"""
    test_app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(test_app)


@pytest.fixture
def ordini_client(test_app, ordini_user) -> TestClient:
    """Client con utente ordini"""
    test_app.dependency_overrides[get_current_user] = lambda: ordini_user
    return TestClient(test_app)


@pytest.fixture
def user_client(test_app, user_user) -> TestClient:
    """Client con utente base"""
    test_app.dependency_overrides[get_current_user] = lambda: user_user
    return TestClient(test_app)


# ============================================================================
# Async Client con Ruoli Predefiniti
# ============================================================================

@pytest_asyncio.fixture
async def admin_client_async(test_app, admin_user) -> AsyncGenerator[AsyncClient, None]:
    """Client async con utente admin"""
    test_app.dependency_overrides[get_current_user] = lambda: admin_user
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def ordini_client_async(test_app, ordini_user) -> AsyncGenerator[AsyncClient, None]:
    """Client async con utente ordini"""
    test_app.dependency_overrides[get_current_user] = lambda: ordini_user
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def user_client_async(test_app, user_user) -> AsyncGenerator[AsyncClient, None]:
    """Client async con utente base"""
    test_app.dependency_overrides[get_current_user] = lambda: user_user
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        yield ac


# ============================================================================
# Carrier Factory Override
# ============================================================================

@pytest.fixture
def fake_carrier_factory(awb: str = "TEST123456789"):
    """Fixture per creare un fake carrier factory"""
    def _factory(carrier_repo: IApiCarrierRepository):
        return FakeCarrierServiceFactory(carrier_repo, awb=awb)
    return _factory


# ============================================================================
# Setup iniziale database
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Setup iniziale del database di test (una volta per sessione)"""
    # Crea le tabelle
    Base.metadata.create_all(bind=test_engine)
    yield
    # Cleanup (opzionale, le tabelle vengono droppate per ogni test)
    # Base.metadata.drop_all(bind=test_engine)
