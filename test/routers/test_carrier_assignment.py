import pytest
from datetime import datetime, date
from sqlalchemy import text
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal
from src.models import CarrierAssignment, CarrierApi, Address, Country, Customer
from src.repository.carrier_assignment_repository import CarrierAssignmentRepository
from src.schemas.carrier_assignment_schema import CarrierAssignmentSchema
from src import get_db
from src.services.auth import get_current_user
from ..utils import override_get_db, override_get_current_user, TestingSessionLocal

# Override dependencies for testing
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)


def get_auth_headers():
    """Helper per ottenere gli header di autenticazione per i test"""
    # Per i test, usiamo un token mock
    return {"Authorization": "Bearer test_token"}


class TestCarrierAssignmentAPI:
    """Test per l'API di CarrierAssignment"""

    @pytest.fixture(autouse=True)
    def setup_test_data(self):
        """Setup dati di test per ogni test"""
        db = TestingSessionLocal()
        
        # Clean up existing data
        db.execute(text("DELETE FROM carrier_assignments"))
        db.execute(text("DELETE FROM carriers_api"))
        db.execute(text("DELETE FROM addresses"))
        db.execute(text("DELETE FROM countries"))
        db.execute(text("DELETE FROM customers"))
        db.commit()
        
        # Create test carrier APIs
        carrier_apis = [
            CarrierApi(name="DHL Express", is_active=True),
            CarrierApi(name="UPS Standard", is_active=True),
            CarrierApi(name="FedEx Priority", is_active=True),
            CarrierApi(name="Poste Italiane", is_active=True),
            CarrierApi(name="Default Carrier", is_active=True)
        ]
        
        for carrier in carrier_apis:
            db.add(carrier)
        db.commit()
        
        # Create test countries
        countries = [
            Country(name="Italia", iso_code="IT", id_origin=1),
            Country(name="Francia", iso_code="FR", id_origin=2),
            Country(name="Germania", iso_code="DE", id_origin=3)
        ]
        
        for country in countries:
            db.add(country)
        db.commit()
        
        # Create test customers
        customers = [
            Customer(
                firstname="Mario", 
                lastname="Rossi", 
                email="mario.rossi@test.com",
                id_origin=1,
                date_add=date.today()
            ),
            Customer(
                firstname="Giulia", 
                lastname="Bianchi", 
                email="giulia.bianchi@test.com",
                id_origin=2,
                date_add=date.today()
            )
        ]
        
        for customer in customers:
            db.add(customer)
        db.commit()
        
        # Create test addresses
        addresses = [
            Address(
                id_origin=1,
                id_country=1,  # Italia
                id_customer=1,
                firstname="Mario",
                lastname="Rossi",
                address1="Via Roma 123",
                postcode="20100",  # Milano
                city="Milano",
                phone="+39 02 1234567",
                date_add=date.today()
            ),
            Address(
                id_origin=2,
                id_country=1,  # Italia
                id_customer=2,
                firstname="Giulia",
                lastname="Bianchi",
                address1="Via Milano 456",
                postcode="00100",  # Roma
                city="Roma",
                phone="+39 06 7654321",
                date_add=date.today()
            ),
            Address(
                id_origin=3,
                id_country=2,  # Francia
                id_customer=1,
                firstname="Mario",
                lastname="Rossi",
                address1="Rue de la Paix 789",
                postcode="75001",  # Parigi
                city="Parigi",
                phone="+33 1 2345678",
                date_add=date.today()
            )
        ]
        
        for address in addresses:
            db.add(address)
        db.commit()
        
        # Create test carrier assignments
        assignments = [
            # Regola 1: DHL per Milano, peso 0-5kg
            CarrierAssignment(
                id_carrier_api=1,  # DHL
                postal_codes="20100,20121,20122,20123,20124,20125,20126,20127,20128,20129,20131,20132,20133,20134,20135,20136,20137,20138,20139,20141,20142,20143,20144,20145,20146,20147,20148,20149,20151,20152,20153,20154,20155,20156,20157,20158,20159,20161,20162,20163,20164,20165,20166,20167,20168,20169,20171,20172,20173,20174,20175,20176,20177,20178,20179,20181,20182,20183,20184,20185,20186,20187,20188,20189,20191,20192,20193,20194,20195,20196,20197,20198,20199",
                countries="1",  # Italia
                min_weight=0.0,
                max_weight=5.0
            ),
            # Regola 2: UPS per Roma, peso 5.1-30kg
            CarrierAssignment(
                id_carrier_api=2,  # UPS
                postal_codes="00100,00118,00119,00120,00121,00122,00123,00124,00125,00126,00127,00128,00129,00131,00132,00133,00134,00135,00136,00137,00138,00139,00141,00142,00143,00144,00145,00146,00147,00148,00149,00151,00152,00153,00154,00155,00156,00157,00158,00159,00161,00162,00163,00164,00165,00166,00167,00168,00169,00171,00172,00173,00174,00175,00176,00177,00178,00179,00181,00182,00183,00184,00185,00186,00187,00188,00189,00191,00192,00193,00194,00195,00196,00197,00198,00199",
                countries="1",  # Italia
                min_weight=5.1,
                max_weight=30.0
            ),
            # Regola 3: FedEx per peso >30kg
            CarrierAssignment(
                id_carrier_api=3,  # FedEx
                countries="1",  # Italia
                min_weight=30.1,
                max_weight=999.0
            ),
            # Regola 4: Poste Italiane per Milano, peso 0-2kg, corrieri origine 1,2,3
            CarrierAssignment(
                id_carrier_api=4,  # Poste Italiane
                postal_codes="20100,20121,20122,20123,20124,20125,20126,20127,20128,20129,20131,20132,20133,20134,20135,20136,20137,20138,20139,20141,20142,20143,20144,20145,20146,20147,20148,20149,20151,20152,20153,20154,20155,20156,20157,20158,20159,20161,20162,20163,20164,20165,20166,20167,20168,20169,20171,20172,20173,20174,20175,20176,20177,20178,20179,20181,20182,20183,20184,20185,20186,20187,20188,20189,20191,20192,20193,20194,20195,20196,20197,20198,20199",
                countries="1",  # Italia
                origin_carriers="1,2,3",
                min_weight=0.0,
                max_weight=2.0
            )
        ]
        
        for assignment in assignments:
            db.add(assignment)
        db.commit()
        
        db.close()

    def test_get_all_carrier_assignments(self):
        """Test per recuperare tutte le assegnazioni"""
        response = client.get("/api/v1/carrier_assignments/", headers=get_auth_headers())
        
        assert response.status_code == 200
        data = response.json()
        assert "carrier_assignments" in data
        assert "total" in data
        assert data["total"] == 4
        assert len(data["carrier_assignments"]) == 4

    def test_get_carrier_assignment_by_id(self):
        """Test per recuperare un'assegnazione per ID"""
        response = client.get("/api/v1/carrier_assignments/1", headers=get_auth_headers())
        
        assert response.status_code == 200
        data = response.json()
        assert data["id_carrier_assignment"] == 1
        assert data["id_carrier_api"] == 1  # DHL

    def test_create_carrier_assignment(self):
        """Test per creare una nuova assegnazione"""
        new_assignment = {
            "id_carrier_api": 5,  # Default Carrier
            "postal_codes": "99999",
            "countries": "1",
            "min_weight": 0.0,
            "max_weight": 10.0
        }
        
        response = client.post("/api/v1/carrier_assignments/", json=new_assignment, headers=get_auth_headers())
        
        assert response.status_code == 201
        data = response.json()
        assert "id_carrier_assignment" in data
        assert data["message"] == "Assegnazione di corriere creata con successo"

    def test_update_carrier_assignment(self):
        """Test per aggiornare un'assegnazione"""
        update_data = {
            "min_weight": 0.0,
            "max_weight": 10.0
        }
        
        response = client.put("/api/v1/carrier_assignments/1", json=update_data, headers=get_auth_headers())
        
        assert response.status_code == 200

    def test_delete_carrier_assignment(self):
        """Test per eliminare un'assegnazione"""
        response = client.delete("/api/v1/carrier_assignments/1", headers=get_auth_headers())
        
        assert response.status_code == 204

    def test_find_matching_assignment(self):
        """Test per trovare un'assegnazione corrispondente"""
        response = client.post(
            "/api/v1/carrier_assignments/find-match",
            params={
                "postal_code": "20100",
                "country_id": 1,
                "weight": 2.5
            },
            headers=get_auth_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Assegnazione trovata"
        assert data["assignment"]["id_carrier_api"] == 1  # DHL


class TestCarrierAssignmentLogic:
    """Test per la logica di assegnazione automatica dei corrieri"""

    @pytest.fixture(autouse=True)
    def setup_test_data(self):
        """Setup dati di test per ogni test"""
        db = TestingSessionLocal()
        
        # Clean up existing data
        db.execute(text("DELETE FROM carrier_assignments"))
        db.execute(text("DELETE FROM carriers_api"))
        db.execute(text("DELETE FROM addresses"))
        db.execute(text("DELETE FROM countries"))
        db.execute(text("DELETE FROM customers"))
        db.commit()
        
        # Create test carrier APIs
        carrier_apis = [
            CarrierApi(name="DHL Express", is_active=True),
            CarrierApi(name="UPS Standard", is_active=True),
            CarrierApi(name="FedEx Priority", is_active=True),
            CarrierApi(name="Poste Italiane", is_active=True),
            CarrierApi(name="Default Carrier", is_active=True)
        ]
        
        for carrier in carrier_apis:
            db.add(carrier)
        db.commit()
        
        # Create test countries
        countries = [
            Country(name="Italia", iso_code="IT", id_origin=1),
            Country(name="Francia", iso_code="FR", id_origin=2),
            Country(name="Germania", iso_code="DE", id_origin=3)
        ]
        
        for country in countries:
            db.add(country)
        db.commit()
        
        # Create test customers
        customers = [
            Customer(
                firstname="Mario", 
                lastname="Rossi", 
                email="mario.rossi@test.com",
                id_origin=1,
                date_add=date.today()
            ),
            Customer(
                firstname="Giulia", 
                lastname="Bianchi", 
                email="giulia.bianchi@test.com",
                id_origin=2,
                date_add=date.today()
            )
        ]
        
        for customer in customers:
            db.add(customer)
        db.commit()
        
        # Create test addresses
        addresses = [
            Address(
                id_origin=1,
                id_country=1,  # Italia
                id_customer=1,
                firstname="Mario",
                lastname="Rossi",
                address1="Via Roma 123",
                postcode="20100",  # Milano
                city="Milano",
                phone="+39 02 1234567",
                date_add=date.today()
            ),
            Address(
                id_origin=2,
                id_country=1,  # Italia
                id_customer=2,
                firstname="Giulia",
                lastname="Bianchi",
                address1="Via Milano 456",
                postcode="00100",  # Roma
                city="Roma",
                phone="+39 06 7654321",
                date_add=date.today()
            ),
            Address(
                id_origin=3,
                id_country=2,  # Francia
                id_customer=1,
                firstname="Mario",
                lastname="Rossi",
                address1="Rue de la Paix 789",
                postcode="75001",  # Parigi
                city="Parigi",
                phone="+33 1 2345678",
                date_add=date.today()
            )
        ]
        
        for address in addresses:
            db.add(address)
        db.commit()
        
        # Create test carrier assignments
        assignments = [
            # Regola 1: DHL per Milano, peso 0-5kg
            CarrierAssignment(
                id_carrier_api=1,  # DHL
                postal_codes="20100,20121,20122,20123,20124,20125,20126,20127,20128,20129,20131,20132,20133,20134,20135,20136,20137,20138,20139,20141,20142,20143,20144,20145,20146,20147,20148,20149,20151,20152,20153,20154,20155,20156,20157,20158,20159,20161,20162,20163,20164,20165,20166,20167,20168,20169,20171,20172,20173,20174,20175,20176,20177,20178,20179,20181,20182,20183,20184,20185,20186,20187,20188,20189,20191,20192,20193,20194,20195,20196,20197,20198,20199",
                countries="1",  # Italia
                min_weight=0.0,
                max_weight=5.0
            ),
            # Regola 2: UPS per Roma, peso 5.1-30kg
            CarrierAssignment(
                id_carrier_api=2,  # UPS
                postal_codes="00100,00118,00119,00120,00121,00122,00123,00124,00125,00126,00127,00128,00129,00131,00132,00133,00134,00135,00136,00137,00138,00139,00141,00142,00143,00144,00145,00146,00147,00148,00149,00151,00152,00153,00154,00155,00156,00157,00158,00159,00161,00162,00163,00164,00165,00166,00167,00168,00169,00171,00172,00173,00174,00175,00176,00177,00178,00179,00181,00182,00183,00184,00185,00186,00187,00188,00189,00191,00192,00193,00194,00195,00196,00197,00198,00199",
                countries="1",  # Italia
                min_weight=5.1,
                max_weight=30.0
            ),
            # Regola 3: FedEx per peso >30kg
            CarrierAssignment(
                id_carrier_api=3,  # FedEx
                countries="1",  # Italia
                min_weight=30.1,
                max_weight=999.0
            ),
            # Regola 4: Poste Italiane per Milano, peso 0-2kg, corrieri origine 1,2,3
            CarrierAssignment(
                id_carrier_api=4,  # Poste Italiane
                postal_codes="20100,20121,20122,20123,20124,20125,20126,20127,20128,20129,20131,20132,20133,20134,20135,20136,20137,20138,20139,20141,20142,20143,20144,20145,20146,20147,20148,20149,20151,20152,20153,20154,20155,20156,20157,20158,20159,20161,20162,20163,20164,20165,20166,20167,20168,20169,20171,20172,20173,20174,20175,20176,20177,20178,20179,20181,20182,20183,20184,20185,20186,20187,20188,20189,20191,20192,20193,20194,20195,20196,20197,20198,20199",
                countries="1",  # Italia
                origin_carriers="1,2,3",
                min_weight=0.0,
                max_weight=2.0
            )
        ]
        
        for assignment in assignments:
            db.add(assignment)
        db.commit()
        
        db.close()

    def test_multiple_conditions_match(self):
        """
        Test per un ordine con più condizioni rispettate in carrier assignment.
        Scenario: Ordine per Milano (20100), Italia (1), peso 1.5kg, corriere origine 2
        Dovrebbe trovare sia la regola DHL che Poste Italiane, ma Poste Italiane dovrebbe avere priorità
        perché ha più condizioni specifiche (postal_code + country + origin_carrier + weight)
        """
        db = TestingSessionLocal()
        repo = CarrierAssignmentRepository(db)
        
        # Test con più condizioni che corrispondono
        assignment = repo.find_matching_assignment(
            postal_code="20100",  # Milano
            country_id=1,         # Italia
            origin_carrier_id=2,  # Corriere origine 2
            weight=1.5           # Peso 1.5kg
        )
        
        assert assignment is not None
        # Poste Italiane dovrebbe avere priorità perché ha più condizioni specifiche
        assert assignment.id_carrier_api == 4  # Poste Italiane
        
        db.close()

    def test_single_condition_match(self):
        """
        Test per un ordine con una sola condizione rispettata in carrier assignment.
        Scenario: Ordine per Roma (00100), Italia (1), peso 15kg
        Dovrebbe trovare solo la regola UPS (postal_code + country + weight)
        """
        db = TestingSessionLocal()
        repo = CarrierAssignmentRepository(db)
        
        # Test con una sola condizione che corrisponde
        assignment = repo.find_matching_assignment(
            postal_code="00100",  # Roma
            country_id=1,         # Italia
            weight=15.0          # Peso 15kg
        )
        
        assert assignment is not None
        assert assignment.id_carrier_api == 2  # UPS
        
        db.close()

    def test_no_conditions_match_default_carrier(self):
        """
        Test per un ordine con nessuna condizione rispettata in carrier assignment.
        Scenario: Ordine per Parigi (75001), Francia (2), peso 5kg
        Non dovrebbe trovare nessuna regola e dovrebbe usare il carrier API di default (ID: 1)
        """
        db = TestingSessionLocal()
        repo = CarrierAssignmentRepository(db)
        
        # Test con nessuna condizione che corrisponde
        assignment = repo.find_matching_assignment(
            postal_code="75001",  # Parigi
            country_id=2,         # Francia
            weight=5.0           # Peso 5kg
        )
        
        # Non dovrebbe trovare nessuna assegnazione
        assert assignment is None
        
        db.close()

    def test_weight_only_condition_match(self):
        """
        Test per un ordine che corrisponde solo per peso.
        Scenario: Ordine per qualsiasi luogo in Italia, peso 50kg
        Dovrebbe trovare la regola FedEx (solo country + weight)
        """
        db = TestingSessionLocal()
        repo = CarrierAssignmentRepository(db)
        
        # Test con solo peso che corrisponde
        assignment = repo.find_matching_assignment(
            postal_code="99999",  # Codice postale non presente nelle regole
            country_id=1,         # Italia
            weight=50.0          # Peso 50kg
        )
        
        assert assignment is not None
        assert assignment.id_carrier_api == 3  # FedEx
        
        db.close()

    def test_country_only_condition_match(self):
        """
        Test per un ordine che corrisponde solo per paese.
        Scenario: Ordine per qualsiasi luogo in Italia, peso 100kg
        Dovrebbe trovare la regola FedEx (solo country + weight)
        """
        db = TestingSessionLocal()
        repo = CarrierAssignmentRepository(db)
        
        # Test con solo paese che corrisponde
        assignment = repo.find_matching_assignment(
            postal_code="99999",  # Codice postale non presente nelle regole
            country_id=1,         # Italia
            weight=100.0         # Peso 100kg
        )
        
        assert assignment is not None
        assert assignment.id_carrier_api == 3  # FedEx
        
        db.close()

    def test_origin_carrier_condition_match(self):
        """
        Test per un ordine che corrisponde per corriere di origine.
        Scenario: Ordine per Milano, Italia, peso 1kg, corriere origine 1
        Dovrebbe trovare la regola Poste Italiane (postal_code + country + origin_carrier + weight)
        """
        db = TestingSessionLocal()
        repo = CarrierAssignmentRepository(db)
        
        # Test con corriere di origine che corrisponde
        assignment = repo.find_matching_assignment(
            postal_code="20100",  # Milano
            country_id=1,         # Italia
            origin_carrier_id=1,  # Corriere origine 1
            weight=1.0           # Peso 1kg
        )
        
        assert assignment is not None
        assert assignment.id_carrier_api == 4  # Poste Italiane
        
        db.close()

    def test_edge_case_weight_boundaries(self):
        """
        Test per i casi limite dei confini di peso.
        """
        db = TestingSessionLocal()
        repo = CarrierAssignmentRepository(db)
        
        # Test peso esatto al limite superiore DHL (5.0kg)
        assignment = repo.find_matching_assignment(
            postal_code="20100",
            country_id=1,
            weight=5.0
        )
        assert assignment is not None
        assert assignment.id_carrier_api == 1  # DHL
        
        # Test peso esatto al limite inferiore UPS (5.1kg)
        assignment = repo.find_matching_assignment(
            postal_code="00100",
            country_id=1,
            weight=5.1
        )
        assert assignment is not None
        assert assignment.id_carrier_api == 2  # UPS
        
        # Test peso esatto al limite superiore UPS (30.0kg)
        assignment = repo.find_matching_assignment(
            postal_code="00100",
            country_id=1,
            weight=30.0
        )
        assert assignment is not None
        assert assignment.id_carrier_api == 2  # UPS
        
        # Test peso esatto al limite inferiore FedEx (30.1kg)
        assignment = repo.find_matching_assignment(
            postal_code="20100",
            country_id=1,
            weight=30.1
        )
        assert assignment is not None
        assert assignment.id_carrier_api == 3  # FedEx
        
        db.close()

    def test_priority_ordering(self):
        """
        Test per verificare che l'ordinamento per priorità funzioni correttamente.
        Le regole con più condizioni specifiche dovrebbero avere priorità.
        """
        db = TestingSessionLocal()
        repo = CarrierAssignmentRepository(db)
        
        # Test che Poste Italiane (4 condizioni) abbia priorità su DHL (3 condizioni)
        assignment = repo.find_matching_assignment(
            postal_code="20100",  # Milano
            country_id=1,         # Italia
            origin_carrier_id=2,  # Corriere origine 2
            weight=1.5           # Peso 1.5kg
        )
        
        assert assignment is not None
        assert assignment.id_carrier_api == 4  # Poste Italiane (più specifica)
        
        db.close()

    def test_no_matching_assignment_returns_none(self):
        """
        Test per verificare che quando non c'è corrispondenza, venga restituito None.
        """
        db = TestingSessionLocal()
        repo = CarrierAssignmentRepository(db)
        
        # Test con parametri che non corrispondono a nessuna regola
        assignment = repo.find_matching_assignment(
            postal_code="99999",  # Codice postale non presente
            country_id=999,       # Paese non presente
            origin_carrier_id=999, # Corriere origine non presente
            weight=999.0         # Peso fuori range
        )
        
        assert assignment is None
        
        db.close()


class TestCarrierAssignmentIntegration:
    """Test di integrazione per il sistema di assegnazione automatica"""

    @pytest.fixture(autouse=True)
    def setup_test_data(self):
        """Setup dati di test per ogni test"""
        db = TestingSessionLocal()
        
        # Clean up existing data
        db.execute(text("DELETE FROM carrier_assignments"))
        db.execute(text("DELETE FROM carriers_api"))
        db.execute(text("DELETE FROM addresses"))
        db.execute(text("DELETE FROM countries"))
        db.execute(text("DELETE FROM customers"))
        db.commit()
        
        # Create test carrier APIs
        carrier_apis = [
            CarrierApi(name="DHL Express", is_active=True),
            CarrierApi(name="UPS Standard", is_active=True),
            CarrierApi(name="FedEx Priority", is_active=True),
            CarrierApi(name="Poste Italiane", is_active=True),
            CarrierApi(name="Default Carrier", is_active=True)
        ]
        
        for carrier in carrier_apis:
            db.add(carrier)
        db.commit()
        
        # Create test countries
        countries = [
            Country(name="Italia", iso_code="IT", id_origin=1),
            Country(name="Francia", iso_code="FR", id_origin=2),
            Country(name="Germania", iso_code="DE", id_origin=3)
        ]
        
        for country in countries:
            db.add(country)
        db.commit()
        
        # Create test customers
        customers = [
            Customer(
                firstname="Mario", 
                lastname="Rossi", 
                email="mario.rossi@test.com",
                id_origin=1,
                date_add=date.today()
            ),
            Customer(
                firstname="Giulia", 
                lastname="Bianchi", 
                email="giulia.bianchi@test.com",
                id_origin=2,
                date_add=date.today()
            )
        ]
        
        for customer in customers:
            db.add(customer)
        db.commit()
        
        # Create test addresses
        addresses = [
            Address(
                id_origin=1,
                id_country=1,  # Italia
                id_customer=1,
                firstname="Mario",
                lastname="Rossi",
                address1="Via Roma 123",
                postcode="20100",  # Milano
                city="Milano",
                phone="+39 02 1234567",
                date_add=date.today()
            ),
            Address(
                id_origin=2,
                id_country=1,  # Italia
                id_customer=2,
                firstname="Giulia",
                lastname="Bianchi",
                address1="Via Milano 456",
                postcode="00100",  # Roma
                city="Roma",
                phone="+39 06 7654321",
                date_add=date.today()
            ),
            Address(
                id_origin=3,
                id_country=2,  # Francia
                id_customer=1,
                firstname="Mario",
                lastname="Rossi",
                address1="Rue de la Paix 789",
                postcode="75001",  # Parigi
                city="Parigi",
                phone="+33 1 2345678",
                date_add=date.today()
            )
        ]
        
        for address in addresses:
            db.add(address)
        db.commit()
        
        # Create test carrier assignments
        assignments = [
            # Regola 1: DHL per Milano, peso 0-5kg
            CarrierAssignment(
                id_carrier_api=1,  # DHL
                postal_codes="20100,20121,20122,20123,20124,20125,20126,20127,20128,20129,20131,20132,20133,20134,20135,20136,20137,20138,20139,20141,20142,20143,20144,20145,20146,20147,20148,20149,20151,20152,20153,20154,20155,20156,20157,20158,20159,20161,20162,20163,20164,20165,20166,20167,20168,20169,20171,20172,20173,20174,20175,20176,20177,20178,20179,20181,20182,20183,20184,20185,20186,20187,20188,20189,20191,20192,20193,20194,20195,20196,20197,20198,20199",
                countries="1",  # Italia
                min_weight=0.0,
                max_weight=5.0
            ),
            # Regola 2: UPS per Roma, peso 5.1-30kg
            CarrierAssignment(
                id_carrier_api=2,  # UPS
                postal_codes="00100,00118,00119,00120,00121,00122,00123,00124,00125,00126,00127,00128,00129,00131,00132,00133,00134,00135,00136,00137,00138,00139,00141,00142,00143,00144,00145,00146,00147,00148,00149,00151,00152,00153,00154,00155,00156,00157,00158,00159,00161,00162,00163,00164,00165,00166,00167,00168,00169,00171,00172,00173,00174,00175,00176,00177,00178,00179,00181,00182,00183,00184,00185,00186,00187,00188,00189,00191,00192,00193,00194,00195,00196,00197,00198,00199",
                countries="1",  # Italia
                min_weight=5.1,
                max_weight=30.0
            ),
            # Regola 3: FedEx per peso >30kg
            CarrierAssignment(
                id_carrier_api=3,  # FedEx
                countries="1",  # Italia
                min_weight=30.1,
                max_weight=999.0
            ),
            # Regola 4: Poste Italiane per Milano, peso 0-2kg, corrieri origine 1,2,3
            CarrierAssignment(
                id_carrier_api=4,  # Poste Italiane
                postal_codes="20100,20121,20122,20123,20124,20125,20126,20127,20128,20129,20131,20132,20133,20134,20135,20136,20137,20138,20139,20141,20142,20143,20144,20145,20146,20147,20148,20149,20151,20152,20153,20154,20155,20156,20157,20158,20159,20161,20162,20163,20164,20165,20166,20167,20168,20169,20171,20172,20173,20174,20175,20176,20177,20178,20179,20181,20182,20183,20184,20185,20186,20187,20188,20189,20191,20192,20193,20194,20195,20196,20197,20198,20199",
                countries="1",  # Italia
                origin_carriers="1,2,3",
                min_weight=0.0,
                max_weight=2.0
            )
        ]
        
        for assignment in assignments:
            db.add(assignment)
        db.commit()
        
        db.close()

    @pytest.mark.anyio
    async def test_carrier_assignment_with_real_order_data(self):
        """
        Test di integrazione con dati di ordine reali.
        Simula il processo di assegnazione automatica durante l'import degli ordini.
        """
        from src.services.ecommerce.prestashop_service import PrestaShopService

        # Mock order data
        order_data = {
            'id': 12345,
            'id_address_delivery': 1,  # Milano
            'id_address_invoice': 1,   # Milano
            'id_carrier': 2,           # Corriere origine 2
            'total_paid_tax_excl': 100.0
        }

        # Mock order total weight
        order_total_weight = 1.5  # kg

        # Create PrestaShopService instance
        db = TestingSessionLocal()
        service = PrestaShopService(db)

        # Test the carrier assignment logic
        assigned_carrier_api_id = await service._assign_carrier_api(
            order=order_data,
            order_total_weight=order_total_weight,
            delivery_address_id=order_data.get('id_address_delivery')
        )

        # Should assign Poste Italiane (ID: 4) because it matches all conditions
        assert assigned_carrier_api_id == 4

        db.close()

    @pytest.mark.anyio
    async def test_carrier_assignment_fallback_to_default(self):
        """
        Test per verificare che quando non c'è corrispondenza, venga usato il carrier API di default.
        """
        from src.services.ecommerce.prestashop_service import PrestaShopService

        # Mock order data for non-matching conditions
        order_data = {
            'id': 12346,
            'id_address_delivery': 3,  # Parigi
            'id_address_invoice': 3,   # Parigi
            'id_carrier': 999,         # Corriere origine non presente
            'total_paid_tax_excl': 200.0
        }

        # Mock order total weight
        order_total_weight = 5.0  # kg

        # Create PrestaShopService instance
        db = TestingSessionLocal()
        service = PrestaShopService(db)

        # Test the carrier assignment logic
        assigned_carrier_api_id = await service._assign_carrier_api(
            order=order_data,
            order_total_weight=order_total_weight,
            delivery_address_id=order_data.get('id_address_delivery')
        )

        # Should fallback to default carrier API (ID: 1)
        assert assigned_carrier_api_id == 1

        db.close()

    @pytest.mark.anyio
    async def test_carrier_assignment_with_missing_address(self):
        """
        Test per verificare il comportamento quando l'indirizzo non esiste.
        """
        from src.services.ecommerce.prestashop_service import PrestaShopService

        # Mock order data with non-existent address
        order_data = {
            'id': 12347,
            'id_address_delivery': 999,  # Indirizzo non esistente
            'id_address_invoice': 999,   # Indirizzo non esistente
            'id_carrier': 1,
            'total_paid_tax_excl': 150.0
        }

        # Mock order total weight
        order_total_weight = 3.0  # kg

        # Create PrestaShopService instance
        db = TestingSessionLocal()
        service = PrestaShopService(db)

        # Test the carrier assignment logic
        assigned_carrier_api_id = await service._assign_carrier_api(
            order=order_data,
            order_total_weight=order_total_weight,
            delivery_address_id=order_data.get('id_address_delivery')
        )

        # Should fallback to default carrier API (ID: 1) when address is not found
        assert assigned_carrier_api_id == 1

        db.close()
