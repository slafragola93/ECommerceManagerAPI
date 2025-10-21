"""
Sistema di monitoring e metrics per l'applicazione
"""
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from collections import defaultdict, deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class MetricData:
    """Struttura per i dati delle metriche"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = None

class MetricsCollector:
    """Raccoglitore di metriche per l'applicazione"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.counters: Dict[str, int] = defaultdict(int)
        self.timers: Dict[str, float] = {}
        self.start_time = datetime.now()
    
    def increment_counter(self, name: str, value: int = 1, tags: Dict[str, str] = None):
        """Incrementa un contatore"""
        self.counters[name] += value
        self._record_metric(name, value, tags)
        logger.debug(f"Counter {name} incremented by {value}")
    
    def record_timer(self, name: str, duration: float, tags: Dict[str, str] = None):
        """Registra un timer"""
        self.timers[name] = duration
        self._record_metric(f"{name}_duration", duration, tags)
        logger.debug(f"Timer {name} recorded: {duration:.3f}s")
    
    def record_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Registra un gauge (valore istantaneo)"""
        self._record_metric(name, value, tags)
        logger.debug(f"Gauge {name} recorded: {value}")
    
    def _record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Registra una metrica"""
        metric = MetricData(
            name=name,
            value=value,
            timestamp=datetime.now(),
            tags=tags or {}
        )
        self.metrics[name].append(metric)
    
    def get_counter(self, name: str) -> int:
        """Ottiene il valore di un contatore"""
        return self.counters.get(name, 0)
    
    def get_timer(self, name: str) -> Optional[float]:
        """Ottiene il valore di un timer"""
        return self.timers.get(name)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Ottiene un riassunto delle metriche"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "uptime_seconds": uptime,
            "uptime_human": str(timedelta(seconds=int(uptime))),
            "counters": dict(self.counters),
            "timers": dict(self.timers),
            "total_metrics": sum(len(metrics) for metrics in self.metrics.values()),
            "metric_names": list(self.metrics.keys())
        }
    
    def get_metric_history(self, name: str, limit: int = 100) -> list:
        """Ottiene la cronologia di una metrica"""
        if name not in self.metrics:
            return []
        
        history = list(self.metrics[name])
        return history[-limit:] if limit else history
    
    def get_average_timer(self, name: str, minutes: int = 5) -> Optional[float]:
        """Calcola la media di un timer negli ultimi N minuti"""
        if name not in self.metrics:
            return None
        
        cutoff = datetime.now() - timedelta(minutes=minutes)
        recent_metrics = [
            m for m in self.metrics[name] 
            if m.timestamp >= cutoff and m.name.endswith('_duration')
        ]
        
        if not recent_metrics:
            return None
        
        return sum(m.value for m in recent_metrics) / len(recent_metrics)

class ErrorTracker:
    """Tracker per errori e eccezioni"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.error_history: deque = deque(maxlen=1000)
        self.last_error: Optional[Dict[str, Any]] = None
    
    def record_error(self, error_type: str, message: str, details: Dict[str, Any] = None):
        """Registra un errore"""
        self.error_counts[error_type] += 1
        
        error_record = {
            "type": error_type,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(),
            "count": self.error_counts[error_type]
        }
        
        self.error_history.append(error_record)
        self.last_error = error_record
        
        logger.error(f"Error tracked: {error_type} - {message}", extra=error_record)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Ottiene un riassunto degli errori"""
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_counts": dict(self.error_counts),
            "last_error": self.last_error,
            "recent_errors": list(self.error_history)[-10:]  # Ultimi 10 errori
        }

class PerformanceMonitor:
    """Monitor delle performance dell'applicazione"""
    
    def __init__(self):
        self.metrics = MetricsCollector()
        self.error_tracker = ErrorTracker()
        self.request_times: deque = deque(maxlen=1000)
        self.active_requests = 0
    
    def start_request(self, path: str, method: str) -> str:
        """Inizia il monitoraggio di una richiesta"""
        request_id = f"{method}_{path}_{int(time.time() * 1000)}"
        self.active_requests += 1
        self.metrics.increment_counter("requests_started", tags={"method": method, "path": path})
        return request_id
    
    def end_request(self, request_id: str, status_code: int, duration: float):
        """Termina il monitoraggio di una richiesta"""
        self.active_requests = max(0, self.active_requests - 1)
        self.request_times.append(duration)
        
        self.metrics.increment_counter("requests_completed")
        self.metrics.record_timer("request_duration", duration)
        
        if status_code >= 400:
            self.metrics.increment_counter("requests_errors")
            self.error_tracker.record_error(
                f"HTTP_{status_code}",
                f"Request failed with status {status_code}",
                {"request_id": request_id, "status_code": status_code}
            )
    
    def record_database_operation(self, operation: str, duration: float, success: bool = True):
        """Registra un'operazione database"""
        self.metrics.increment_counter("database_operations", tags={"operation": operation})
        self.metrics.record_timer(f"db_{operation}", duration)
        
        if not success:
            self.metrics.increment_counter("database_errors", tags={"operation": operation})
            self.error_tracker.record_error(
                "DATABASE_ERROR",
                f"Database operation failed: {operation}",
                {"operation": operation, "duration": duration}
            )
    
    def record_cache_operation(self, operation: str, hit: bool = True):
        """Registra un'operazione cache"""
        self.metrics.increment_counter("cache_operations", tags={"operation": operation})
        
        if hit:
            self.metrics.increment_counter("cache_hits", tags={"operation": operation})
        else:
            self.metrics.increment_counter("cache_misses", tags={"operation": operation})
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Ottiene un riassunto delle performance"""
        avg_response_time = (
            sum(self.request_times) / len(self.request_times) 
            if self.request_times else 0
        )
        
        return {
            "active_requests": self.active_requests,
            "average_response_time": avg_response_time,
            "total_requests": self.metrics.get_counter("requests_completed"),
            "error_rate": (
                self.metrics.get_counter("requests_errors") / 
                max(1, self.metrics.get_counter("requests_completed"))
            ),
            "cache_hit_rate": (
                self.metrics.get_counter("cache_hits") / 
                max(1, self.metrics.get_counter("cache_operations"))
            ),
            "metrics": self.metrics.get_metrics_summary(),
            "errors": self.error_tracker.get_error_summary()
        }

# Istanza globale del monitor
performance_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """Ottiene l'istanza globale del monitor delle performance"""
    return performance_monitor
