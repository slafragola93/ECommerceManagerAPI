"""
Test di integrazione per gli endpoint Category
Testa sia i casi OK che gli errori (404, 400, 409, 422, 401, 403)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient
from fastapi import status

from src.models.category import Category
from src.schemas.category_schema import CategorySchema
from src.services.interfaces.category_service_interface import ICategoryService
from src.core.exceptions import NotFoundException, BusinessRuleException, ValidationException
from src.routers.category import get_category_service
from tests.helpers.asserts import assert_success_response, assert_error_response


# ============================================================================
# Mock Category Service
# ============================================================================

class FakeCategoryService(ICategoryService):
    """Mock service per i test degli endpoint Category"""
    
    def __init__(self):
        self.categories: dict[int, Category] = {}
        self.next_id = 1
        self.should_raise_not_found = False
        self.should_raise_business_rule = False
        self.should_raise_validation = False
        self.not_found_id = None
        self.duplicate_name = None
    
    def _create_category_model(self, category_data: CategorySchema, category_id: int = None) -> Category:
        """Helper per creare un modello Category"""
        if category_id is None:
            category_id = self.next_id
            self.next_id += 1
        
        return Category(
            id_category=category_id,
            id_origin=category_data.id_origin or 0,
            id_store=1,
            name=category_data.name
        )
    
    async def create_category(self, category_data: CategorySchema) -> Category:
        """Crea una nuova categoria"""
        if self.should_raise_validation:
            raise ValidationException("Errore nella creazione della categoria")
        
        if self.duplicate_name and category_data.name == self.duplicate_name:
            raise BusinessRuleException(
                f"Categoria con nome '{category_data.name}' già esistente",
                details={"name": category_data.name}
            )
        
        category = self._create_category_model(category_data)
        self.categories[category.id_category] = category
        return category
    
    async def update_category(self, category_id: int, category_data: CategorySchema) -> Category:
        """Aggiorna una categoria esistente"""
        if self.should_raise_not_found or category_id not in self.categories:
            raise NotFoundException("Category", category_id)
        
        if self.should_raise_validation:
            raise ValidationException("Errore nell'aggiornamento della categoria")
        
        if self.duplicate_name and category_data.name == self.duplicate_name:
            existing = self.categories.get(category_id)
            if not existing or existing.name != category_data.name:
                raise BusinessRuleException(
                    f"Categoria con nome '{category_data.name}' già esistente",
                    details={"name": category_data.name}
                )
        
        category = self.categories[category_id]
        category.name = category_data.name
        if category_data.id_origin is not None:
            category.id_origin = category_data.id_origin
        return category
    
    async def get_category(self, category_id: int) -> Category:
        """Ottiene una categoria per ID"""
        if self.should_raise_not_found or category_id not in self.categories:
            raise NotFoundException("Category", category_id)
        return self.categories[category_id]
    
    async def get_categories(self, page: int = 1, limit: int = 10, **filters) -> list[Category]:
        """Ottiene la lista delle categorie"""
        if self.should_raise_validation:
            raise ValidationException("Errore nel recupero delle categorie")
        
        categories_list = list(self.categories.values())
        start = (page - 1) * limit
        end = start + limit
        return categories_list[start:end]
    
    async def delete_category(self, category_id: int) -> bool:
        """Elimina una categoria"""
        if self.should_raise_not_found or category_id not in self.categories:
            raise NotFoundException("Category", category_id)
        
        if self.should_raise_validation:
            raise ValidationException("Errore nell'eliminazione della categoria")
        
        del self.categories[category_id]
        return True
    
    async def get_categories_count(self, **filters) -> int:
        """Ottiene il numero totale di categorie"""
        return len(self.categories)
    
    async def validate_business_rules(self, data) -> None:
        """Valida le regole business"""
        pass


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def fake_category_service() -> FakeCategoryService:
    """Fixture che fornisce un FakeCategoryService pulito"""
    return FakeCategoryService()


@pytest.fixture
def category_sample_data() -> dict:
    """Dati di esempio per una categoria"""
    return {
        "id_origin": 100,
        "id_platform": 0,
        "name": "Elettronica"
    }


@pytest.fixture
def category_sample_data_2() -> dict:
    """Altri dati di esempio per una categoria"""
    return {
        "id_origin": 200,
        "id_platform": 0,
        "name": "Abbigliamento"
    }


# ============================================================================
# GET /api/v1/categories/
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_all_categories_success(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict,
    category_sample_data_2: dict
):
    """✅ GET /categories/ - 200 con lista + total + page + limit"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Crea alcune categorie
    await fake_category_service.create_category(CategorySchema(**category_sample_data))
    await fake_category_service.create_category(CategorySchema(**category_sample_data_2))
    
    # Act
    response = await admin_client_async.get("/api/v1/categories/", params={"page": 1, "limit": 10})
    
    # Assert
    assert_success_response(response, status_code=status.HTTP_200_OK)
    data = response.json()
    assert "categories" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert data["total"] == 2
    assert len(data["categories"]) == 2
    assert data["page"] == 1
    assert data["limit"] == 10


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_all_categories_empty_404(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ GET /categories/ - 404 se categories vuoto"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await admin_client_async.get("/api/v1/categories/", params={"page": 1, "limit": 10})
    
    # Assert
    assert_error_response(
        response,
        status_code=status.HTTP_404_NOT_FOUND,
        error_code="ENTITY_NOT_FOUND"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_all_categories_unauthorized(
    test_app,
    async_client: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ GET /categories/ - 401 se non autenticato"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act (senza header Authorization)
    response = await async_client.get("/api/v1/categories/")
    
    # Assert
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_all_categories_forbidden(
    test_app,
    user_client_async: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ GET /categories/ - 403 se autenticato ma ruolo non valido"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act (user_client_async ha ruolo USER, non ADMIN)
    response = await user_client_async.get("/api/v1/categories/")
    
    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# GET /api/v1/categories/{id}
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_category_by_id_success(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """✅ GET /categories/{id} - 200 categoria"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    category = await fake_category_service.create_category(CategorySchema(**category_sample_data))
    
    # Act
    response = await admin_client_async.get(f"/api/v1/categories/{category.id_category}")
    
    # Assert
    assert_success_response(response, status_code=status.HTTP_200_OK)
    data = response.json()
    assert data["id_category"] == category.id_category
    assert data["name"] == category_sample_data["name"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_category_by_id_not_found(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ GET /categories/{id} - 404 se non esiste"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    fake_category_service.should_raise_not_found = True
    
    # Act
    response = await admin_client_async.get("/api/v1/categories/999")
    
    # Assert
    assert_error_response(
        response,
        status_code=status.HTTP_404_NOT_FOUND,
        error_code="ENTITY_NOT_FOUND"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_category_by_id_invalid_id(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ GET /categories/{id} - 422 se id non valido (Path gt=0)"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await admin_client_async.get("/api/v1/categories/0")
    
    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_category_by_id_unauthorized(
    test_app,
    async_client: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ GET /categories/{id} - 401 se non autenticato"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await async_client.get("/api/v1/categories/1")
    
    # Assert
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_category_by_id_forbidden(
    test_app,
    user_client_async: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ GET /categories/{id} - 403 se autenticato ma ruolo non valido"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await user_client_async.get("/api/v1/categories/1")
    
    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# POST /api/v1/categories/
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_category_success(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """✅ POST /categories/ - 201 crea"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await admin_client_async.post("/api/v1/categories/", json=category_sample_data)
    
    # Assert
    assert_success_response(response, status_code=status.HTTP_201_CREATED)
    data = response.json()
    assert "id_category" in data
    assert data["name"] == category_sample_data["name"]
    assert data["id_origin"] == category_sample_data["id_origin"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_category_duplicate_name(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """❌ POST /categories/ - 400 se nome duplicato (BusinessRuleException)"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    fake_category_service.duplicate_name = category_sample_data["name"]
    await fake_category_service.create_category(CategorySchema(**category_sample_data))
    
    # Act
    response = await admin_client_async.post("/api/v1/categories/", json=category_sample_data)
    
    # Assert
    assert_error_response(
        response,
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code="BUSINESS_RULE_VIOLATION",
        message_contains="già esistente"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_category_invalid_payload(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ POST /categories/ - 422 payload non valido"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act (manca il campo obbligatorio "name")
    response = await admin_client_async.post("/api/v1/categories/", json={"id_origin": 100})
    
    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_category_unauthorized(
    test_app,
    async_client: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """❌ POST /categories/ - 401 se non autenticato"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await async_client.post("/api/v1/categories/", json=category_sample_data)
    
    # Assert
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_category_forbidden(
    test_app,
    user_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """❌ POST /categories/ - 403 se autenticato ma ruolo non valido"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await user_client_async.post("/api/v1/categories/", json=category_sample_data)
    
    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# PUT /api/v1/categories/{id}
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_category_success(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """✅ PUT /categories/{id} - 200 update"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    category = await fake_category_service.create_category(CategorySchema(**category_sample_data))
    
    update_data = {
        "id_origin": 300,
        "id_platform": 0,
        "name": "Elettronica Aggiornata"
    }
    
    # Act
    response = await admin_client_async.put(
        f"/api/v1/categories/{category.id_category}",
        json=update_data
    )
    
    # Assert
    assert_success_response(response, status_code=status.HTTP_200_OK)
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["id_origin"] == update_data["id_origin"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_category_not_found(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """❌ PUT /categories/{id} - 404 se non esiste"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    fake_category_service.should_raise_not_found = True
    
    # Act
    response = await admin_client_async.put("/api/v1/categories/999", json=category_sample_data)
    
    # Assert
    assert_error_response(
        response,
        status_code=status.HTTP_404_NOT_FOUND,
        error_code="ENTITY_NOT_FOUND"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_category_duplicate_name(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict,
    category_sample_data_2: dict
):
    """❌ PUT /categories/{id} - 400 se nome duplicato"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    category1 = await fake_category_service.create_category(CategorySchema(**category_sample_data))
    category2 = await fake_category_service.create_category(CategorySchema(**category_sample_data_2))
    
    # Prova ad aggiornare category1 con il nome di category2
    update_data = {
        "id_origin": category_sample_data["id_origin"],
        "id_platform": 0,
        "name": category_sample_data_2["name"]  # Nome duplicato
    }
    
    # Act
    response = await admin_client_async.put(
        f"/api/v1/categories/{category1.id_category}",
        json=update_data
    )
    
    # Assert
    assert_error_response(
        response,
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code="BUSINESS_RULE_VIOLATION",
        message_contains="già esistente"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_category_invalid_payload(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """❌ PUT /categories/{id} - 422 payload non valido"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    category = await fake_category_service.create_category(CategorySchema(**category_sample_data))
    
    # Act (manca il campo obbligatorio "name")
    response = await admin_client_async.put(
        f"/api/v1/categories/{category.id_category}",
        json={"id_origin": 100}
    )
    
    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_category_invalid_id(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """❌ PUT /categories/{id} - 422 id non valido (Path gt=0)"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await admin_client_async.put("/api/v1/categories/0", json=category_sample_data)
    
    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_category_unauthorized(
    test_app,
    async_client: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """❌ PUT /categories/{id} - 401 se non autenticato"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await async_client.put("/api/v1/categories/1", json=category_sample_data)
    
    # Assert
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_category_forbidden(
    test_app,
    user_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """❌ PUT /categories/{id} - 403 se autenticato ma ruolo non valido"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await user_client_async.put("/api/v1/categories/1", json=category_sample_data)
    
    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# DELETE /api/v1/categories/{id}
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_category_success(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService,
    category_sample_data: dict
):
    """✅ DELETE /categories/{id} - 200 (anche se non ritorni body)"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    category = await fake_category_service.create_category(CategorySchema(**category_sample_data))
    
    # Act
    response = await admin_client_async.delete(f"/api/v1/categories/{category.id_category}")
    
    # Assert
    assert_success_response(response, status_code=status.HTTP_200_OK)
    
    # Verifica che la categoria sia stata eliminata
    count = await fake_category_service.get_categories_count()
    assert count == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_category_not_found(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ DELETE /categories/{id} - 404 se non esiste"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    fake_category_service.should_raise_not_found = True
    
    # Act
    response = await admin_client_async.delete("/api/v1/categories/999")
    
    # Assert
    assert_error_response(
        response,
        status_code=status.HTTP_404_NOT_FOUND,
        error_code="ENTITY_NOT_FOUND"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_category_invalid_id(
    test_app,
    admin_client_async: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ DELETE /categories/{id} - 422 id non valido (Path gt=0)"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await admin_client_async.delete("/api/v1/categories/0")
    
    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_category_unauthorized(
    test_app,
    async_client: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ DELETE /categories/{id} - 401 se non autenticato"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await async_client.delete("/api/v1/categories/1")
    
    # Assert
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_category_forbidden(
    test_app,
    user_client_async: AsyncClient,
    fake_category_service: FakeCategoryService
):
    """❌ DELETE /categories/{id} - 403 se autenticato ma ruolo non valido"""
    # Arrange
    test_app.dependency_overrides[get_category_service] = lambda: fake_category_service
    
    # Act
    response = await user_client_async.delete("/api/v1/categories/1")
    
    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN
