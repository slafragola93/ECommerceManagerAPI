"""
Dependency Resolver for CSV Import System.

Manages entity dependencies and determines correct import order.
Follows Single Responsibility Principle - only handles dependency logic.
"""
from __future__ import annotations

from typing import List, Dict, Set, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text


class DependencyResolver:
    """
    Risolve dipendenze tra entità e determina ordine import corretto.
    
    Implementa topological sort per ordinamento dipendenze.
    """
    
    # Grafo dipendenze: {entity: [lista dipendenze]}
    DEPENDENCY_GRAPH: Dict[str, List[str]] = {
        # Layer 1: Nessuna dipendenza
        'languages': [],
        'countries': [],
        'payments': [],
        'brands': [],
        'categories': [],
        'carriers': [],
        
        # Layer 2: Dipendono da Layer 1
        'customers': ['languages'],
        
        # Layer 3: Dipendono da Layer 2
        'addresses': ['customers', 'countries'],
        'products': ['categories', 'brands'],
        
        # Layer 4: Dipendono da Layer 3
        'orders': ['customers', 'addresses', 'payments', 'carriers'],
        
        # Layer 5: Dipendono da Layer 4
        'order_details': ['orders', 'products']
    }
    
    # Mapping entity_type → table_name per check DB
    TABLE_MAPPING: Dict[str, str] = {
        'languages': 'languages',
        'countries': 'countries',
        'payments': 'payments',
        'brands': 'brands',
        'categories': 'categories',
        'carriers': 'carriers',
        'customers': 'customers',
        'addresses': 'addresses',
        'products': 'products',
        'orders': 'orders',
        'order_details': 'order_details'
    }
    
    @staticmethod
    def get_dependencies(entity_type: str) -> List[str]:
        """
        Ottiene lista dipendenze per un tipo entità.
        
        Args:
            entity_type: Tipo entità
            
        Returns:
            Lista nomi dipendenze
        """
        return DependencyResolver.DEPENDENCY_GRAPH.get(entity_type, [])
    
    @staticmethod
    def get_import_order(entity_types: List[str]) -> List[str]:
        """
        Determina ordine corretto import per lista entità usando topological sort.
        
        Args:
            entity_types: Lista tipi entità da importare
            
        Returns:
            Lista ordinata per import (dipendenze prima)
        """
        # Se single entity, return as-is
        if len(entity_types) == 1:
            return entity_types
        
        # Build dependency graph for requested entities
        graph = {entity: [] for entity in entity_types}
        for entity in entity_types:
            deps = DependencyResolver.get_dependencies(entity)
            # Include only dependencies that are in the import list
            graph[entity] = [dep for dep in deps if dep in entity_types]
        
        # Topological sort (Kahn's algorithm)
        in_degree = {entity: 0 for entity in entity_types}
        for entity in entity_types:
            for dep in graph[entity]:
                in_degree[dep] += 1
        
        queue = [entity for entity in entity_types if in_degree[entity] == 0]
        sorted_order = []
        
        while queue:
            # Sort queue for deterministic order
            queue.sort()
            current = queue.pop(0)
            sorted_order.append(current)
            
            for entity in entity_types:
                if current in graph[entity]:
                    in_degree[current] -= 1
                    if in_degree[current] == 0:
                        queue.append(current)
        
        # Reverse because we built the graph backwards
        return sorted_order
    
    @staticmethod
    def validate_dependencies(
        entity_type: str, 
        db: Session,
        id_store: Optional[int] = None
    ) -> Tuple[bool, List[str]]:
        """
        Valida che tutte le dipendenze siano popolate nel database.
        
        Args:
            entity_type: Tipo entità da importare
            db: Sessione database
            id_store: ID store (opzionale, per entity store-specific)
            
        Returns:
            Tuple (is_valid, missing_dependencies)
        """
        dependencies = DependencyResolver.get_dependencies(entity_type)
        
        if not dependencies:
            return True, []
        
        missing = []
        
        for dep in dependencies:
            table_name = DependencyResolver.TABLE_MAPPING.get(dep)
            if not table_name:
                continue
            
            try:
                # Check se la tabella ha records
                # Per tabelle platform-aware, controlla solo per platform specifico
                if dep in ['products', 'addresses', 'orders', 'customers'] and id_store is not None:
                    query = text(f"SELECT COUNT(*) FROM {table_name} WHERE id_store = :id_store")
                    count = db.execute(query, {"id_store": id_store}).scalar()
                else:
                    query = text(f"SELECT COUNT(*) FROM {table_name}")
                    count = db.execute(query).scalar()
                
                if count == 0:
                    missing.append(dep)
                    
            except Exception as e:
                print(f"WARNING: Error checking dependency '{dep}': {str(e)}")
                missing.append(dep)
        
        return len(missing) == 0, missing
    
    @staticmethod
    def get_all_dependencies_recursive(entity_type: str) -> Set[str]:
        """
        Ottiene tutte le dipendenze ricorsive per un'entità.
        
        Args:
            entity_type: Tipo entità
            
        Returns:
            Set di tutte le dipendenze (dirette e indirette)
        """
        dependencies = set()
        
        def _get_deps(entity: str):
            deps = DependencyResolver.get_dependencies(entity)
            for dep in deps:
                if dep not in dependencies:
                    dependencies.add(dep)
                    _get_deps(dep)
        
        _get_deps(entity_type)
        return dependencies

