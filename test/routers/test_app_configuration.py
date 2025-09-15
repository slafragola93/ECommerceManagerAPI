from src import get_db
from src.main import app
from src.models import AppConfiguration
from src.services.auth import get_current_user
from ..utils import client, test_app_configuration, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

# Risultati attesi per i test
expected_results = [
    {
        "id_app_configuration": 5,
        "id_lang": 0,
        "category": "api_keys",
        "name": "app_api_key",
        "value": "secret_api_key_123",
        "description": "Chiave API App",
        "is_encrypted": True
    },
    {
        "id_app_configuration": 4,
        "id_lang": 0,
        "category": "email_settings",
        "name": "sender_email",
        "value": "noreply@elettronew.com",
        "description": "Email mittente",
        "is_encrypted": False
    },
    {
        "id_app_configuration": 3,
        "id_lang": 0,
        "category": "electronic_invoicing",
        "name": "tax_regime",
        "value": "RF01",
        "description": "Regime fiscale",
        "is_encrypted": False
    },
    {
        "id_app_configuration": 2,
        "id_lang": 0,
        "category": "company_info",
        "name": "vat_number",
        "value": "02469660209",
        "description": "Partita IVA",
        "is_encrypted": False
    },
    {
        "id_app_configuration": 1,
        "id_lang": 0,
        "category": "company_info",
        "name": "company_name",
        "value": "Elettronew S.r.l.",
        "description": "Ragione sociale",
        "is_encrypted": False
    }
]


# ==================== TEST ENDPOINT CRUD ====================

def test_get_all_app_configs(test_app_configuration):
    """Test per recuperare tutte le configurazioni app"""
    response = client.get("/api/v1/app-configs/")

    assert response.status_code == 200
    data = response.json()
    assert len(data["configurations"]) == 5
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["limit"] == 100


def test_get_all_app_configs_with_pagination(test_app_configuration):
    """Test per recuperare configurazioni con paginazione"""
    response = client.get("/api/v1/app-configs/?page=1&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert len(data["configurations"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["limit"] == 2


def test_get_app_config_by_id(test_app_configuration):
    """Test per recuperare una configurazione per ID"""
    response = client.get('/api/v1/app-configs/1')

    assert response.status_code == 200
    data = response.json()
    assert data["id_app_configuration"] == 1
    assert data["name"] == "company_name"
    assert data["category"] == "company_info"
    assert data["value"] == "Elettronew S.r.l."

    # Test per configurazione non esistente
    response = client.get('/api/v1/app-configs/999')
    assert response.status_code == 404


def test_get_app_configs_by_category(test_app_configuration):
    """Test per recuperare configurazioni per categoria"""
    response = client.get('/api/v1/app-configs/category/company_info')

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(config["category"] == "company_info" for config in data)

    # Test per categoria non esistente
    response = client.get('/api/v1/app-configs/category/nonexistent')
    assert response.status_code == 404


def test_get_app_configs_by_category_grouped(test_app_configuration):
    """Test per recuperare configurazioni raggruppate per categoria"""
    response = client.get('/api/v1/app-configs/by-category')

    assert response.status_code == 200
    data = response.json()
    assert data["total_categories"] == 4
    assert data["total_configurations"] == 5
    
    categories = data["categories"]
    assert len(categories) == 4
    
    # Verifica che le categorie siano presenti
    category_names = [cat["category"] for cat in categories]
    assert "company_info" in category_names
    assert "electronic_invoicing" in category_names
    assert "email_settings" in category_names
    assert "api_keys" in category_names


def test_get_app_config_value(test_app_configuration):
    """Test per recuperare il valore di una configurazione specifica"""
    response = client.get('/api/v1/app-configs/value/company_info/company_name')

    assert response.status_code == 200
    data = response.json()
    assert data["value"] == "Elettronew S.r.l."

    # Test per configurazione non esistente
    response = client.get('/api/v1/app-configs/value/nonexistent/nonexistent')
    assert response.status_code == 404


def test_create_app_config(test_app_configuration):
    """Test per creare una nuova configurazione"""
    request_body = {
        "id_lang": 0,
        "category": "company_info",
        "name": "test_config",
        "value": "test_value",
        "description": "Test configuration",
        "is_encrypted": False
    }

    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 201

    # Verifica che la configurazione sia stata creata
    db = TestingSessionLocal()
    config = db.query(AppConfiguration).filter(
        AppConfiguration.name == "test_config",
        AppConfiguration.category == "company_info"
    ).first()
    assert config is not None
    assert config.value == "test_value"
    assert config.description == "Test configuration"
    assert config.is_encrypted == False

    # Test per configurazione duplicata
    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 400


def test_create_bulk_app_configs(test_app_configuration):
    """Test per creare multiple configurazioni in batch"""
    request_body = [
        {
            "id_lang": 0,
            "category": "test_category",
            "name": "bulk_config_1",
            "value": "bulk_value_1",
            "description": "Bulk test 1",
            "is_encrypted": False
        },
        {
            "id_lang": 0,
            "category": "test_category",
            "name": "bulk_config_2",
            "value": "bulk_value_2",
            "description": "Bulk test 2",
            "is_encrypted": False
        }
    ]

    response = client.post("/api/v1/app-configs/bulk", json=request_body)
    assert response.status_code == 201

    # Verifica che le configurazioni siano state create
    db = TestingSessionLocal()
    configs = db.query(AppConfiguration).filter(
        AppConfiguration.category == "test_category"
    ).all()
    assert len(configs) == 2


def test_update_app_config(test_app_configuration):
    """Test per aggiornare una configurazione"""
    request_body = {
        "value": "Updated Company Name",
        "description": "Updated description"
    }

    response = client.put("/api/v1/app-configs/1", json=request_body)
    assert response.status_code == 204

    # Verifica che la configurazione sia stata aggiornata
    db = TestingSessionLocal()
    config = db.query(AppConfiguration).filter(AppConfiguration.id_app_configuration == 1).first()
    assert config.value == "Updated Company Name"
    assert config.description == "Updated description"

    # Test per configurazione non esistente
    response = client.put("/api/v1/app-configs/999", json=request_body)
    assert response.status_code == 404


def test_update_app_config_value(test_app_configuration):
    """Test per aggiornare il valore di una configurazione specifica"""
    response = client.put("/api/v1/app-configs/value/company_info/company_name?value=New Company Name")
    assert response.status_code == 204

    # Verifica che il valore sia stato aggiornato
    db = TestingSessionLocal()
    config = db.query(AppConfiguration).filter(
        AppConfiguration.name == "company_name",
        AppConfiguration.category == "company_info"
    ).first()
    assert config.value == "New Company Name"

    # Test per configurazione non esistente
    response = client.put("/api/v1/app-configs/value/nonexistent/nonexistent?value=test")
    assert response.status_code == 404


def test_delete_app_config(test_app_configuration):
    """Test per eliminare una configurazione per ID"""
    response = client.delete("/api/v1/app-configs/5")
    assert response.status_code == 204

    # Verifica che la configurazione sia stata eliminata
    db = TestingSessionLocal()
    config = db.query(AppConfiguration).filter(AppConfiguration.id_app_configuration == 5).first()
    assert config is None

    # Test per configurazione non esistente
    response = client.delete("/api/v1/app-configs/999")
    assert response.status_code == 404


def test_delete_app_config_by_name(test_app_configuration):
    """Test per eliminare una configurazione per nome e categoria"""
    response = client.delete("/api/v1/app-configs/email_settings/sender_email")
    assert response.status_code == 204

    # Verifica che la configurazione sia stata eliminata
    db = TestingSessionLocal()
    config = db.query(AppConfiguration).filter(
        AppConfiguration.name == "sender_email",
        AppConfiguration.category == "email_settings"
    ).first()
    assert config is None

    # Test per configurazione non esistente
    response = client.delete("/api/v1/app-configs/nonexistent/nonexistent")
    assert response.status_code == 404


# ==================== TEST ENDPOINT SPECIFICI PER CATEGORIA ====================

def test_get_company_info(test_app_configuration):
    """Test per recuperare le configurazioni di anagrafica azienda"""
    response = client.get("/api/v1/app-configs/company-info")

    assert response.status_code == 200
    data = response.json()
    # Gli schema Pydantic restituiscono tutti i campi, anche se None
    assert data["company_name"] == "Elettronew S.r.l."
    assert data["vat_number"] == "02469660209"
    # Altri campi dovrebbero essere None
    assert data["company_logo"] is None


def test_get_electronic_invoicing(test_app_configuration):
    """Test per recuperare le configurazioni di fatturazione elettronica"""
    response = client.get("/api/v1/app-configs/electronic-invoicing")

    assert response.status_code == 200
    data = response.json()
    assert data["tax_regime"] == "RF01"
    # Altri campi dovrebbero essere None
    assert data["transmitter_fiscal_code"] is None


def test_get_exempt_rates(test_app_configuration):
    """Test per recuperare le configurazioni di aliquote esenti"""
    response = client.get("/api/v1/app-configs/exempt-rates")

    assert response.status_code == 200
    data = response.json()
    # Tutti i campi dovrebbero essere None per default
    assert data["exempt_rate_standard"] is None
    assert data["exempt_rate_no"] is None
    assert data["exempt_rate_no_x"] is None


def test_get_fatturapa(test_app_configuration):
    """Test per recuperare le configurazioni Fatturapa"""
    response = client.get("/api/v1/app-configs/fatturapa")

    assert response.status_code == 200
    data = response.json()
    # Il campo api_key dovrebbe essere None per default
    assert data["api_key"] is None


def test_get_email_settings(test_app_configuration):
    """Test per recuperare le configurazioni email"""
    response = client.get("/api/v1/app-configs/email-settings")

    assert response.status_code == 200
    data = response.json()
    assert data["sender_email"] == "noreply@elettronew.com"
    # Altri campi dovrebbero essere None
    assert data["sender_name"] is None


def test_get_api_keys(test_app_configuration):
    """Test per recuperare le chiavi API dell'app"""
    response = client.get("/api/v1/app-configs/api-keys")

    assert response.status_code == 200
    data = response.json()
    assert data["app_api_key"] == "secret_api_key_123"


# ==================== TEST PERMESSI E AUTORIZZAZIONI ====================

def test_get_app_configs_with_user_permissions(test_app_configuration):
    """Test per verificare che gli utenti senza permessi non possano accedere"""
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/app-configs/")
    assert response.status_code == 403


def test_get_app_config_by_id_with_user_permissions(test_app_configuration):
    """Test per verificare che gli utenti senza permessi non possano accedere per ID"""
    response = client.get('/api/v1/app-configs/1')
    assert response.status_code == 403


def test_create_app_config_with_user_permissions(test_app_configuration):
    """Test per verificare che gli utenti senza permessi non possano creare"""
    request_body = {
        "id_lang": 0,
        "category": "test_category",
        "name": "test_config",
        "value": "test_value",
        "description": "Test configuration",
        "is_encrypted": False
    }

    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 403


def test_update_app_config_with_user_permissions(test_app_configuration):
    """Test per verificare che gli utenti senza permessi non possano aggiornare"""
    request_body = {
        "value": "Updated value"
    }
    response = client.put("/api/v1/app-configs/1", json=request_body)
    assert response.status_code == 403


def test_delete_app_config_with_user_permissions(test_app_configuration):
    """Test per verificare che gli utenti senza permessi non possano eliminare"""
    response = client.delete("/api/v1/app-configs/1")
    assert response.status_code == 403


def test_get_company_info_with_user_permissions(test_app_configuration):
    """Test per verificare che gli utenti senza permessi non possano accedere alle categorie"""
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/app-configs/company-info")
    assert response.status_code == 403

    # Ripristina i permessi admin per i test successivi
    app.dependency_overrides[get_current_user] = override_get_current_user


# ==================== TEST CASI DI ERRORE ====================

def test_create_app_config_invalid_data(test_app_configuration):
    """Test per creare configurazione con dati non validi"""
    # Test senza nome
    request_body = {
        "id_lang": 0,
        "category": "test_category",
        "value": "test_value"
    }
    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 422

    # Test senza categoria
    request_body = {
        "id_lang": 0,
        "name": "test_config",
        "value": "test_value"
    }
    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 422


def test_update_app_config_invalid_data(test_app_configuration):
    """Test per aggiornare configurazione con dati non validi"""
    # Test con ID non valido
    request_body = {
        "value": "Updated value"
    }
    response = client.put("/api/v1/app-configs/0", json=request_body)
    assert response.status_code == 422

    # Test con ID negativo
    response = client.put("/api/v1/app-configs/-1", json=request_body)
    assert response.status_code == 422


def test_get_app_config_invalid_id(test_app_configuration):
    """Test per recuperare configurazione con ID non valido"""
    # Test con ID 0
    response = client.get('/api/v1/app-configs/0')
    assert response.status_code == 422

    # Test con ID negativo
    response = client.get('/api/v1/app-configs/-1')
    assert response.status_code == 422


def test_pagination_invalid_parameters(test_app_configuration):
    """Test per paginazione con parametri non validi"""
    # Assicurati di usare l'utente admin
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Test con pagina 0
    response = client.get("/api/v1/app-configs/?page=0")
    assert response.status_code == 422

    # Test con limite 0
    response = client.get("/api/v1/app-configs/?limit=0")
    assert response.status_code == 422

    # Test con limite troppo alto
    response = client.get("/api/v1/app-configs/?limit=1001")
    assert response.status_code == 422


def test_bulk_create_invalid_data(test_app_configuration):
    """Test per creazione bulk con dati non validi"""
    # Assicurati di usare l'utente admin
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Test con array vuoto
    response = client.post("/api/v1/app-configs/bulk", json=[])
    assert response.status_code == 422

    # Test con dati non validi
    request_body = [
        {
            "id_lang": 0,
            "category": "test_category",
            # Manca il nome
            "value": "test_value"
        }
    ]
    response = client.post("/api/v1/app-configs/bulk", json=request_body)
    assert response.status_code == 422


# ==================== TEST VALIDAZIONE SCHEMA ====================

def test_app_config_schema_validation(test_app_configuration):
    """Test per validazione degli schema Pydantic"""
    # Test con descrizione troppo lunga
    request_body = {
        "id_lang": 0,
        "category": "test_category",
        "name": "test_config",
        "value": "test_value",
        "description": "x" * 300,  # Troppo lunga
        "is_encrypted": False
    }
    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 422

    # Test con nome troppo lungo
    request_body = {
        "id_lang": 0,
        "category": "test_category",
        "name": "x" * 150,  # Troppo lungo
        "value": "test_value",
        "description": "Test description",
        "is_encrypted": False
    }
    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 422

    # Test con categoria troppo lunga
    request_body = {
        "id_lang": 0,
        "category": "x" * 100,  # Troppo lunga
        "name": "test_config",
        "value": "test_value",
        "description": "Test description",
        "is_encrypted": False
    }
    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 422


# ==================== TEST CASI EDGE ====================

def test_empty_database(test_app_configuration):
    """Test per database vuoto"""
    # Assicurati di usare l'utente admin
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Prima elimina tutte le configurazioni
    db = TestingSessionLocal()
    db.query(AppConfiguration).delete()
    db.commit()
    db.close()

    # Test per lista vuota
    response = client.get("/api/v1/app-configs/")
    assert response.status_code == 404

    # Test per categoria vuota
    response = client.get("/api/v1/app-configs/category/company_info")
    assert response.status_code == 404

    # Test per configurazione per categoria vuota
    response = client.get("/api/v1/app-configs/by-category")
    assert response.status_code == 200
    data = response.json()
    assert data["total_categories"] == 0
    assert data["total_configurations"] == 0
    assert data["categories"] == []


def test_unicode_values(test_app_configuration):
    """Test per valori Unicode"""
    # Assicurati di usare l'utente admin
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    request_body = {
        "id_lang": 0,
        "category": "test_category",
        "name": "unicode_test",
        "value": "Valore con caratteri speciali: àèéìòù €£$",
        "description": "Test con caratteri Unicode",
        "is_encrypted": False
    }

    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 201

    # Verifica che il valore sia stato salvato correttamente
    response = client.get("/api/v1/app-configs/value/test_category/unicode_test")
    assert response.status_code == 200
    data = response.json()
    assert data["value"] == "Valore con caratteri speciali: àèéìòù €£$"


def test_encrypted_vs_unencrypted(test_app_configuration):
    """Test per configurazioni criptate vs non criptate"""
    # Assicurati di usare l'utente admin
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Test configurazione non criptata
    request_body = {
        "id_lang": 0,
        "category": "test_category",
        "name": "unencrypted_test",
        "value": "plain_text_value",
        "description": "Test non criptato",
        "is_encrypted": False
    }

    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 201

    # Test configurazione criptata
    request_body = {
        "id_lang": 0,
        "category": "test_category",
        "name": "encrypted_test",
        "value": "secret_value",
        "description": "Test criptato",
        "is_encrypted": True
    }

    response = client.post("/api/v1/app-configs/", json=request_body)
    assert response.status_code == 201

    # Verifica che entrambe siano state salvate
    db = TestingSessionLocal()
    unencrypted = db.query(AppConfiguration).filter(
        AppConfiguration.name == "unencrypted_test"
    ).first()
    encrypted = db.query(AppConfiguration).filter(
        AppConfiguration.name == "encrypted_test"
    ).first()

    assert unencrypted is not None
    assert encrypted is not None
    assert unencrypted.is_encrypted == False
    assert encrypted.is_encrypted == True
