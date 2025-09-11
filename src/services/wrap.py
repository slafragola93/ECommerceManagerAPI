import time
from functools import wraps

from fastapi import HTTPException


def check_authentication(func):
    """
      Decoratore per verificare se un utente è autenticato prima di permettere l'accesso a una funzione.

      Questo decoratore prende una funzione e verifica se l'argomento 'user' è presente e non None.
      Se l'utente non è autenticato (ovvero 'user' è None), solleva un'eccezione HTTPException con status 401.
      Se l'utente è autenticato, permette alla funzione originale di essere eseguita.

      Parametri:
          func (Callable): La funzione asincrona da decorare che richiede autenticazione.

      Ritorna:
          Callable: Una funzione wrapper asincrona che esegue il controllo di autenticazione.

      Solleva:
          HTTPException: Se non viene trovato un utente autenticato nei parametri della funzione.

      Utilizzo:
          Decorare qualsiasi endpoint FastAPI che richieda autenticazione dell'utente. Assicurarsi
          che 'user' sia passato come parametro keyword alla funzione decorata.
      """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        user = kwargs.get('user', None)
        
        if user is None:
            raise HTTPException(status_code=401, detail="Utente non autenticato")
        print(user)
        
        return await func(*args, **kwargs)

    return wrapper


def timing_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Tempo di esecuzione di {func.__name__}: {execution_time:.4f} secondi")
        return await func(*args, **kwargs)

    return wrapper
