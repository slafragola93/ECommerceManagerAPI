"""
Dependency injection per FastAPI seguendo DIP
"""
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session
from src.database import get_db
from src.core.container import container

# Type aliases per le dipendenze
db_dependency = Annotated[Session, Depends(get_db)]

def get_container():
    """Ottiene il container di dependency injection"""
    return container

def resolve_dependency(interface_type):
    """Risolve una dipendenza dal container"""
    return container.resolve(interface_type)

# Factory functions per le dipendenze comuni
def create_dependency_resolver(interface_type):
    """Crea una funzione di dependency resolution per un'interfaccia"""
    def resolver():
        return container.resolve(interface_type)
    return resolver

# Decorator per dependency injection automatica
def inject_dependencies(func):
    """Decorator per iniettare automaticamente le dipendenze"""
    import inspect
    
    signature = inspect.signature(func)
    
    def wrapper(*args, **kwargs):
        # Risolve le dipendenze mancanti
        for param_name, param in signature.parameters.items():
            if param_name not in kwargs and param.annotation != inspect.Parameter.empty:
                try:
                    kwargs[param_name] = container.resolve(param.annotation)
                except ValueError:
                    # Se non può essere risolto, lascia il parametro come è
                    pass
        
        return func(*args, **kwargs)
    
    return wrapper
