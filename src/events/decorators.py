"""Decorators for automatic event emission."""

from __future__ import annotations

import inspect
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional

from .core.event import Event, EventType
from .runtime import emit_event

logger = logging.getLogger(__name__)


def emit_event_on_success(
    event_type: EventType,
    data_extractor: Optional[Callable[..., Dict[str, Any]]] = None,
    metadata_extractor: Optional[Callable[..., Dict[str, Any]]] = None,
    source: Optional[str] = None,
    condition: Optional[Callable[..., bool]] = None,
):
    """
    Decorator to automatically emit an event after a function successfully executes.
    
    Args:
        event_type: The type of event to emit
        data_extractor: Optional function to extract event data from function args/kwargs/result.
                       Signature: (*args, **kwargs, result) -> Dict[str, Any]
                       If None, uses default extraction based on common parameter names.
        metadata_extractor: Optional function to extract metadata from function args/kwargs/result.
                          Signature: (*args, **kwargs, result) -> Dict[str, Any]
                          If None, uses default extraction.
        source: Optional source identifier for metadata. If None, uses function module and name.
        condition: Optional function to determine if event should be emitted.
                   Signature: (*args, **kwargs, result) -> bool
                   If None, event is always emitted (unless data extraction fails).
    
    Usage:
        @emit_event_on_success(
            event_type=EventType.ORDER_STATUS_CHANGED,
            data_extractor=lambda *args, **kwargs, result: {
                "order_id": kwargs.get("order_id"),
                "old_state_id": kwargs.get("old_state_id"),
                "new_state_id": kwargs.get("new_status_id"),
            },
            source="order_router.update_order_status"
        )
        async def update_order_status(...):
            ...
    """
    
    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)
        
        def _emit_event_logic(result: Any, *args, **kwargs) -> Any:
            """Common logic for emitting events (used by both sync and async wrappers)"""
            # Check condition if provided
            if condition:
                try:
                    if not condition(*args, result=result, **kwargs):
                        return result
                except Exception as e:
                    logger.warning(
                        "Failed to evaluate condition for %s: %s",
                        func.__name__,
                        e,
                        exc_info=True,
                    )
                    return result
            
            # Extract event data
            if data_extractor:
                try:
                    event_data = data_extractor(*args, result=result, **kwargs)
                    # Skip event if data extraction returns None or empty dict
                    if not event_data:
                        return result
                except Exception as e:
                    logger.warning(
                        "Failed to extract event data for %s: %s",
                        func.__name__,
                        e,
                        exc_info=True,
                    )
                    return result
            else:
                # Default extraction: try to find common parameters
                event_data = _extract_default_data(*args, result=result, **kwargs)
                # Skip if no data extracted
                if not event_data:
                    return result
            
            # Extract metadata
            if metadata_extractor:
                try:
                    metadata = metadata_extractor(*args, result=result, **kwargs)
                except Exception as e:
                    logger.warning(
                        "Failed to extract metadata for %s: %s",
                        func.__name__,
                        e,
                        exc_info=True,
                    )
                    metadata = {}
            else:
                metadata = _extract_default_metadata(
                    func, *args, result=result, source=source, **kwargs
                )
            
            # Create and emit event
            event = Event(
                event_type=event_type.value,
                data=event_data,
                metadata=metadata,
            )
            
            try:
                emit_event(event)
            except Exception:  # pragma: no cover - safeguard event system failures
                logger.exception(
                    "Failed to emit %s event for function %s",
                    event_type.value,
                    func.__name__,
                )
            
            return result
        
        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Execute the original async function
                result = await func(*args, **kwargs)
                return _emit_event_logic(result, *args, **kwargs)
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Execute the original sync function
                result = func(*args, **kwargs)
                return _emit_event_logic(result, *args, **kwargs)
            
            return sync_wrapper
    
    return decorator


def _extract_default_data(*args, result=None, **kwargs) -> Dict[str, Any]:
    """Extract default event data from function arguments."""
    data = {}
    
    # Try to extract common parameters
    common_keys = ["order_id", "id_order", "id", "customer_id", "product_id"]
    for key in common_keys:
        if key in kwargs:
            data[key] = kwargs[key]
    
    # Try to extract from args if they're dict-like
    for arg in args:
        if isinstance(arg, dict):
            for key in common_keys:
                if key in arg and key not in data:
                    data[key] = arg[key]
    
    return data


def _extract_default_metadata(
    func: Callable,
    *args,
    result: Any = None,
    source: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Extract default metadata from function context."""
    metadata = {}
    
    # Set source
    if source:
        metadata["source"] = source
    else:
        module = func.__module__ if hasattr(func, "__module__") else "unknown"
        metadata["source"] = f"{module}.{func.__name__}"
    
    # Try to extract order_id for metadata
    order_id = kwargs.get("order_id") or kwargs.get("id_order")
    if order_id:
        metadata["id_order"] = order_id
    
    return metadata

