"""
Dependency Injection Container seguendo il principio DIP (Dependency Inversion Principle)
"""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Dict, Any, Callable, Type, Optional
from functools import lru_cache
import inspect

T = TypeVar('T')

class Container:
    """Dependency Injection Container seguendo DIP"""
    
    def __init__(self):
        self._services: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._transients: Dict[str, Type] = {}
    
    def register_singleton(self, interface: Type[T], implementation: Type[T]):
        """Registra un servizio come singleton"""
        key = self._get_key(interface)
        self._services[key] = lambda: self._get_or_create_singleton(key, implementation)
    
    def register_transient(self, interface: Type[T], implementation: Type[T]):
        """Registra un servizio come transient (nuova istanza ogni volta)"""
        key = self._get_key(interface)
        self._transients[key] = implementation
    
    def register_instance(self, interface: Type[T], instance: T):
        """Registra un'istanza specifica"""
        key = self._get_key(interface)
        self._singletons[key] = instance
    
    def resolve(self, interface: Type[T]) -> T:
        """Risolve una dipendenza"""
        key = self._get_key(interface)
        
        if key in self._services:
            return self._services[key]()
        elif key in self._transients:
            return self._create_instance(self._transients[key])
        elif key in self._singletons:
            return self._singletons[key]
        else:
            raise ValueError(f"Cannot resolve {interface.__name__}: No registration found")
    
    def _get_key(self, interface: Type[T]) -> str:
        """Ottiene la chiave per un'interfaccia"""
        return interface.__name__
    
    def _get_or_create_singleton(self, key: str, implementation: Type[T]) -> T:
        """Ottiene o crea un singleton"""
        if key not in self._singletons:
            self._singletons[key] = self._create_instance(implementation)
        return self._singletons[key]
    
    def _create_instance(self, implementation: Type[T]) -> T:
        """Crea una nuova istanza con dependency injection"""
        # Ottieni la firma del costruttore
        signature = inspect.signature(implementation.__init__)
        
        # Costruisci gli argomenti
        kwargs = {}
        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            
            # Prova a risolvere il tipo del parametro
            param_type = param.annotation
            if param_type != inspect.Parameter.empty:
                try:
                    kwargs[param_name] = self.resolve(param_type)
                except ValueError:
                    # Se non può essere risolto, usa il valore di default
                    if param.default != inspect.Parameter.empty:
                        kwargs[param_name] = param.default
                    else:
                        # Per parametri come Session, crea un'istanza None che verrà iniettata successivamente
                        if param_name == 'session':
                            kwargs[param_name] = None
                        else:
                            raise ValueError(f"Cannot resolve parameter {param_name} of type {param_type}")
        
        return implementation(**kwargs)
    
    def is_registered(self, interface: Type[T]) -> bool:
        """Verifica se un'interfaccia è registrata"""
        key = self._get_key(interface)
        return key in self._services or key in self._transients or key in self._singletons
    
    def resolve_with_session(self, interface: Type[T], session) -> T:
        """Risolve una dipendenza iniettando una sessione DB"""
        key = self._get_key(interface)
        
        if key in self._transients:
            # Crea una nuova istanza iniettando la sessione
            implementation = self._transients[key]
            
            # Se è un servizio, crea le dipendenze con la sessione
            if hasattr(implementation, '__init__'):
                import inspect
                sig = inspect.signature(implementation.__init__)
                kwargs = {}
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    elif param_name == 'session':
                        kwargs[param_name] = session
                    else:
                        # Risolve le altre dipendenze
                        try:
                            kwargs[param_name] = self.resolve_with_session(param.annotation, session)
                        except:
                            kwargs[param_name] = self.resolve(param.annotation)
                
                return implementation(**kwargs)
            else:
                return implementation(session)
        elif key in self._services:
            # Per i singleton, inietta la sessione nell'istanza esistente
            instance = self._services[key]()
            if hasattr(instance, '_session'):
                instance._session = session
            return instance
        else:
            raise ValueError(f"Cannot resolve {interface.__name__} with session")
    
    def clear(self):
        """Pulisce il container"""
        self._services.clear()
        self._singletons.clear()
        self._transients.clear()
        print("Container pulito")

# Global container instance
container = Container()

# Decorator per registrazione automatica
def register_singleton(interface: Type[T]):
    """Decorator per registrare automaticamente un servizio come singleton"""
    def decorator(implementation: Type[T]):
        container.register_singleton(interface, implementation)
        return implementation
    return decorator

def register_transient(interface: Type[T]):
    """Decorator per registrare automaticamente un servizio come transient"""
    def decorator(implementation: Type[T]):
        container.register_transient(interface, implementation)
        return implementation
    return decorator
