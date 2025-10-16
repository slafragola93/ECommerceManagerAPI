# 🏗️ Architettura SOLID - ECommerceManagerAPI

## 📋 Panoramica

L'ECommerceManagerAPI è stato completamente rifattorizzato seguendo i **principi SOLID** per garantire un'architettura scalabile, mantenibile e testabile. Questa documentazione descrive il workflow completo della nuova architettura.

## 🎯 Principi SOLID Applicati

### 1. **Single Responsibility Principle (SRP)**
- Ogni classe ha una singola responsabilità ben definita
- Repository: solo accesso ai dati
- Service: solo logica business
- Router: solo gestione HTTP

### 2. **Open/Closed Principle (OCP)**
- Sistema aperto per estensioni, chiuso per modifiche
- Nuovi router possono essere aggiunti senza modificare il codice esistente
- Interfacce permettono nuove implementazioni

### 3. **Liskov Substitution Principle (LSP)**
- Le implementazioni concrete possono essere sostituite senza alterare il comportamento
- BaseRepository può essere sostituito da implementazioni specifiche

### 4. **Interface Segregation Principle (ISP)**
- Interfacce specifiche per ogni responsabilità
- Clienti dipendono solo dai metodi che utilizzano

### 5. **Dependency Inversion Principle (DIP)**
- Dipendenze verso astrazioni, non concrezioni
- Dependency Injection Container per gestione dipendenze

## 🏛️ Architettura a Livelli

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   FastAPI       │  │   Router        │  │   Schemas    │ │
│  │   Application   │  │   (HTTP)        │  │ (Validation) │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     BUSINESS LAYER                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Service       │  │   Interfaces    │  │   Business   │ │
│  │   (Logic)       │  │   (Contracts)   │  │   Rules      │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA ACCESS LAYER                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Repository    │  │   Base Repo     │  │   Models     │ │
│  │   (Data Access) │  │   (CRUD)        │  │ (SQLAlchemy) │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Database      │  │   DI Container  │  │   Cache      │ │
│  │   (MySQL)       │  │   (Dependencies)│  │   (Redis)    │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 Workflow Completo

### 1. **Richiesta HTTP**
```http
GET /api/v1/customers?page=1&limit=10
Authorization: Bearer <token>
```

### 2. **Router Layer**
```python
@router.get("/", response_model=AllCustomerResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_customers(
    user: user_dependency,
    customer_service: ICustomerService = Depends(get_customer_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    # Validazione parametri HTTP
    # Autenticazione e autorizzazione
    # Delegazione al Service Layer
```

### 3. **Dependency Injection**
```python
def get_customer_service(db: db_dependency) -> ICustomerService:
    # Configurazione container DI
    configured_container = get_configured_container()
    
    # Risoluzione dipendenze
    customer_repo = configured_container.resolve_with_session(ICustomerRepository, db)
    customer_service = configured_container.resolve(ICustomerService)
    
    # Iniezione dipendenza
    customer_service._customer_repository = customer_repo
    
    return customer_service
```

### 4. **Service Layer**
```python
class CustomerService(ICustomerService):
    def __init__(self, customer_repository: ICustomerRepository):
        self._customer_repository = customer_repository
    
    async def get_customers(self, page: int = 1, limit: int = 10, **filters) -> List[Customer]:
        # Validazione parametri business
        # Applicazione regole business
        # Delegazione al Repository Layer
        customers = self._customer_repository.get_all(**filters)
        return customers
```

### 5. **Repository Layer**
```python
class CustomerRepository(BaseRepository[Customer, int], ICustomerRepository):
    def __init__(self, session: Session):
        super().__init__(session, Customer)
    
    def get_all(self, **filters) -> List[Customer]:
        # Costruzione query SQLAlchemy
        # Applicazione filtri
        # Esecuzione query
        # Gestione errori database
        query = self._session.query(self._model_class)
        query = self._apply_filters(query, filters)
        return query.all()
```

### 6. **BaseRepository (CRUD Generico)**
```python
class BaseRepository(Generic[T, K], ABC):
    def __init__(self, session: Session, model_class: Type[T]):
        self._session = session
        self._model_class = model_class
    
    def create(self, entity: T) -> T:
        # Commit automatico
        # Refresh per ottenere ID generato
        self._session.add(entity)
        self._session.commit()
        self._session.refresh(entity)
        return entity
```

### 7. **Risposta HTTP**
```json
{
  "customers": [...],
  "total": 150,
  "page": 1,
  "limit": 10
}
```

## 🧩 Componenti Architetturali

### **1. Dependency Injection Container**
```python
# src/core/container.py
class Container:
    def register_transient(self, interface: Type[T], implementation: Type[T]):
        """Registra servizio come transient"""
    
    def resolve_with_session(self, interface: Type[T], session: Any) -> T:
        """Risolve dipendenza iniettando sessione DB"""
```

### **2. Interfacce Repository**
```python
# src/repository/interfaces/customer_repository_interface.py
class ICustomerRepository(IRepository[Customer, int]):
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[Customer]:
        pass
```

### **3. Repository Implementazioni**
```python
# src/repository/customer_repository.py
class CustomerRepository(BaseRepository[Customer, int], ICustomerRepository):
    def get_by_email(self, email: str) -> Optional[Customer]:
        return self._session.query(Customer).filter(
            func.lower(Customer.email) == func.lower(email)
        ).first()
```

### **4. Interfacce Service**
```python
# src/services/interfaces/customer_service_interface.py
class ICustomerService(IBaseService):
    @abstractmethod
    async def create_customer(self, customer_data: CustomerSchema) -> Customer:
        pass
```

### **5. Service Implementazioni**
```python
# src/services/customer_service.py
class CustomerService(ICustomerService):
    def __init__(self, customer_repository: ICustomerRepository):
        self._customer_repository = customer_repository
    
    async def create_customer(self, customer_data: CustomerSchema) -> Customer:
        # Validazioni business
        # Creazione entità
        # Gestione errori
```

### **6. Gestione Errori Centralizzata**
```python
# src/core/exceptions.py
class ValidationException(DomainException):
    def __init__(self, message: str, error_code: str = ErrorCode.VALIDATION_ERROR):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, error_code=error_code)
```

## 📁 Struttura File

```
src/
├── core/                          # Componenti core dell'architettura
│   ├── container.py              # DI Container
│   ├── container_config.py       # Configurazione container
│   ├── base_repository.py        # Repository base generico
│   ├── interfaces.py             # Interfacce base
│   ├── exceptions.py             # Gerarchia eccezioni
│   └── dependencies.py           # Dipendenze FastAPI
├── repository/                   # Data Access Layer
│   ├── interfaces/               # Interfacce repository
│   │   ├── customer_repository_interface.py
│   │   ├── user_repository_interface.py
│   │   └── ...
│   ├── customer_repository.py    # Implementazioni repository
│   ├── user_repository.py
│   └── ...
├── services/                     # Business Layer
│   ├── interfaces/               # Interfacce service
│   │   ├── customer_service_interface.py
│   │   ├── user_service_interface.py
│   │   └── ...
│   ├── customer_service.py       # Implementazioni service
│   ├── user_service.py
│   └── ...
└── routers/                      # Presentation Layer
    ├── customer.py               # Router SOLID
    ├── user.py
    └── ...
```

## 🔧 Configurazione Container DI

```python
# src/core/container_config.py
def configure_container():
    # Repository - Transient (nuova istanza per ogni richiesta)
    container.register_transient(ICustomerRepository, CustomerRepository)
    container.register_transient(IUserRepository, UserRepository)
    
    # Services - Transient (nuova istanza per ogni richiesta)
    container.register_transient(ICustomerService, CustomerService)
    container.register_transient(IUserService, UserService)
```

## 🚀 Vantaggi dell'Architettura

### **1. Maintainability**
- Codice modulare e ben organizzato
- Separazione netta delle responsabilità
- Facile localizzazione e correzione bug

### **2. Testability**
- Dipendenze iniettate facilmente mockabili
- Interfacce permettono test isolati
- Business logic testabile indipendentemente

### **3. Scalability**
- Nuovi router aggiungibili senza modifiche
- Pattern consolidati per estensioni
- Architettura uniforme in tutto il progetto

### **4. Flexibility**
- Implementazioni intercambiabili
- Configurazione centralizzata
- Facile sostituzione componenti

### **5. Consistency**
- Pattern uniformi in tutto il progetto
- Gestione errori standardizzata
- Struttura prevedibile

## 📊 Esempio di Flusso Completo

### **Creazione Customer**

1. **HTTP Request**
```http
POST /api/v1/customers
Content-Type: application/json
Authorization: Bearer <token>

{
  "firstname": "Mario",
  "lastname": "Rossi",
  "email": "mario.rossi@example.com",
  "id_lang": 1
}
```

2. **Router Validation**
```python
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer: CustomerSchema,  # Validazione automatica Pydantic
    customer_service: ICustomerService = Depends(get_customer_service)
):
    return await customer_service.create_customer(customer)
```

3. **Business Logic**
```python
async def create_customer(self, customer_data: CustomerSchema) -> Customer:
    # Validazione email unica
    existing = self._customer_repository.get_by_email(customer_data.email)
    if existing:
        raise ExceptionFactory.email_duplicate(customer_data.email)
    
    # Creazione customer
    customer = Customer(**customer_data.dict())
    customer.date_add = date.today()
    return self._customer_repository.create(customer)
```

4. **Database Operation**
```python
def create(self, entity: T) -> T:
    self._session.add(entity)
    self._session.commit()      # Commit automatico
    self._session.refresh(entity)  # Refresh per ID generato
    return entity
```

5. **HTTP Response**
```json
{
  "id_customer": 123,
  "firstname": "Mario",
  "lastname": "Rossi",
  "email": "mario.rossi@example.com",
  "date_add": "2024-01-15"
}
```

## 🎯 Best Practices Implementate

### **1. Error Handling**
- Gerarchia di eccezioni personalizzate
- Mapping automatico a HTTP status codes
- Messaggi di errore standardizzati

### **2. Validation**
- Validazione Pydantic negli schemi
- Validazioni business nel service layer
- Validazione parametri HTTP nei router

### **3. Security**
- Autenticazione centralizzata
- Autorizzazione basata su ruoli
- Validazione input rigorosa

### **4. Performance**
- Lazy loading per relazioni
- Paginazione automatica
- Cache integrata

### **5. Documentation**
- OpenAPI/Swagger automatico
- Docstring dettagliate
- Esempi di utilizzo

## 🔄 Estensione del Sistema

### **Aggiungere Nuovo Router**

1. **Creare Interfacce**
```python
# src/repository/interfaces/product_repository_interface.py
class IProductRepository(IRepository[Product, int]):
    @abstractmethod
    def get_by_sku(self, sku: str) -> Optional[Product]:
        pass
```

2. **Implementare Repository**
```python
# src/repository/product_repository.py
class ProductRepository(BaseRepository[Product, int], IProductRepository):
    def get_by_sku(self, sku: str) -> Optional[Product]:
        return self._session.query(Product).filter(Product.sku == sku).first()
```

3. **Creare Service**
```python
# src/services/product_service.py
class ProductService(IProductService):
    async def create_product(self, product_data: ProductSchema) -> Product:
        # Business logic
        pass
```

4. **Configurare Container**
```python
# src/core/container_config.py
container.register_transient(IProductRepository, ProductRepository)
container.register_transient(IProductService, ProductService)
```

5. **Router Automatico**
```python
# src/routers/product.py
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductSchema,
    product_service: IProductService = Depends(get_product_service)
):
    return await product_service.create_product(product)
```

## 📈 Metriche di Qualità

- **Cyclomatic Complexity**: Ridotta significativamente
- **Code Duplication**: Eliminata tramite BaseRepository
- **Coupling**: Ridotto tramite DI Container
- **Cohesion**: Aumentata tramite SRP
- **Test Coverage**: Migliorata tramite dependency injection

## 🎉 Conclusioni

L'architettura SOLID implementata garantisce:

✅ **Manutenibilità**: Codice pulito e organizzato
✅ **Scalabilità**: Facile aggiunta di nuove funzionalità  
✅ **Testabilità**: Componenti isolati e mockabili
✅ **Flessibilità**: Implementazioni intercambiabili
✅ **Consistenza**: Pattern uniformi in tutto il progetto

Il sistema è ora pronto per evoluzioni future mantenendo alta qualità del codice e facilità di manutenzione.
