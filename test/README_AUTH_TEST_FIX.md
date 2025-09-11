# Correzione Test di Autenticazione

## Problema Risolto

Il test `test_get_current_user_valid_token` stava fallendo con l'errore:
```
fastapi.exceptions.HTTPException: 401: Token non valido o scaduto
```

## Causa del Problema

Il problema era causato da una **discrepanza nella SECRET_KEY** utilizzata per creare e validare i token JWT:

1. **Creazione del token**: Il test usava `SECRET_KEY` importato da `src.routers.auth`, che poteva essere `None` se la variabile d'ambiente non era impostata
2. **Validazione del token**: La funzione `get_current_user` usava `os.environ.get("SECRET_KEY")`, che era impostata a `"test-secret-key"` in `test_config.py`

## Soluzione Implementata

### 1. Import della Configurazione di Test
Aggiunto l'import di `test_config.py` in `test_auth.py`:
```python
from ..test_config import *  # Importa la configurazione di test per SECRET_KEY
```

### 2. Uso della Stessa Chiave
Modificato il test per usare la stessa chiave segreta:
```python
@pytest.mark.asyncio
async def test_get_current_user_valid_token():
    import os
    # Usa la stessa chiave che usa get_current_user
    test_secret_key = os.environ.get("SECRET_KEY", "test-secret-key")
    
    encode = {"sub": "test_user", "id": 1, "roles": [{"name": "ADMIN", "permissions": "CRUD"}]}
    token = jwt.encode(encode, test_secret_key, algorithm=ALHORITHM)

    user = await get_current_user(token=token)
    assert user == {"username": "test_user", "id": 1, "roles": [{"name": "ADMIN", "permissions": "CRUD"}]}
```

## File Modificati

- `test/routers/test_auth.py`: Aggiunto import di `test_config` e modificato il test per usare la chiave corretta

## Risultato

✅ **Tutti i test di autenticazione ora passano:**
```bash
10 passed, 16 warnings in 7.19s
```

## Test Verificati

- ✅ `test_login_success` (asyncio e trio)
- ✅ `test_login_fail` (asyncio e trio)
- ✅ `test_authenticate_user`
- ✅ `test_create_access_token`
- ✅ `test_get_current_user_valid_token` ← **CORRETTO**
- ✅ `test_get_current_user_invalid_token`
- ✅ `test_create_user_success`
- ✅ `test_create_user_duplicate`

## Note Importanti

1. **Configurazione Test**: Il file `test_config.py` imposta `SECRET_KEY = "test-secret-key"` per tutti i test
2. **Consistenza**: È importante che la stessa chiave segreta sia usata sia per creare che per validare i token
3. **Variabili d'Ambiente**: I test devono sempre importare la configurazione di test per avere le variabili d'ambiente corrette

## Come Eseguire i Test

```bash
# Tutti i test di autenticazione
pytest test/routers/test_auth.py -v

# Solo il test specifico
pytest test/routers/test_auth.py::test_get_current_user_valid_token -v
```

## Prevenzione Futura

Per evitare problemi simili in futuro:
1. Sempre importare `test_config.py` nei test che usano JWT
2. Usare `os.environ.get("SECRET_KEY")` invece di importare `SECRET_KEY` direttamente
3. Verificare che la stessa chiave sia usata per creare e validare i token
