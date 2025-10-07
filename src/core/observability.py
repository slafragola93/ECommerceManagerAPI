"""
Observability and metrics for cache operations
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
import asyncio

from .settings import get_cache_settings

logger = logging.getLogger(__name__)


class CacheMetrics:
    """Cache performance metrics collector"""
    
    def __init__(self):
        self.settings = get_cache_settings()
        self._counters = defaultdict(int)
        self._histograms = defaultdict(list)
        self._gauges = defaultdict(float)
        self._start_times = {}
        
        # Circular buffers for recent metrics
        self._recent_hits = deque(maxlen=1000)
        self._recent_misses = deque(maxlen=1000)
        self._recent_latencies = deque(maxlen=1000)
        
        # Last reset time
        self._last_reset = datetime.now()
    
    def record_hit(self, layer: str, key_pattern: str, ttl_remaining: Optional[int] = None):
        """Record cache hit"""
        self._counters[f"cache_hit_total_{layer}_{key_pattern}"] += 1
        self._counters[f"cache_hit_total_{layer}"] += 1
        self._counters["cache_hit_total"] += 1
        
        # Record in recent buffer
        self._recent_hits.append({
            "timestamp": time.time(),
            "layer": layer,
            "pattern": key_pattern,
            "ttl_remaining": ttl_remaining
        })
        
        logger.debug(f"Cache hit: {layer}:{key_pattern}")
    
    def record_miss(self, layer: str, key_pattern: str):
        """Record cache miss"""
        self._counters[f"cache_miss_total_{layer}_{key_pattern}"] += 1
        self._counters[f"cache_miss_total_{layer}"] += 1
        self._counters["cache_miss_total"] += 1
        
        # Record in recent buffer
        self._recent_misses.append({
            "timestamp": time.time(),
            "layer": layer,
            "pattern": key_pattern
        })
        
        logger.debug(f"Cache miss: {layer}:{key_pattern}")
    
    def record_latency(self, operation: str, layer: str, latency_ms: float):
        """Record operation latency"""
        self._histograms[f"cache_latency_{operation}_{layer}"].append(latency_ms)
        self._histograms[f"cache_latency_{operation}"].append(latency_ms)
        
        # Record in recent buffer
        self._recent_latencies.append({
            "timestamp": time.time(),
            "operation": operation,
            "layer": layer,
            "latency_ms": latency_ms
        })
        
        logger.debug(f"Cache latency: {operation}:{layer} = {latency_ms}ms")
    
    def record_error(self, operation: str, layer: str, error_type: str):
        """Record cache error"""
        self._counters[f"cache_error_total_{layer}_{error_type}"] += 1
        self._counters[f"cache_error_total_{layer}"] += 1
        self._counters["cache_error_total"] += 1
        
        logger.warning(f"Cache error: {operation}:{layer}:{error_type}")
    
    def record_size(self, layer: str, size_bytes: int):
        """Record cache size"""
        self._gauges[f"cache_size_bytes_{layer}"] = size_bytes
        self._gauges["cache_size_bytes_total"] += size_bytes
    
    def record_eviction(self, layer: str, reason: str):
        """Record cache eviction"""
        self._counters[f"cache_eviction_total_{layer}_{reason}"] += 1
        self._counters[f"cache_eviction_total_{layer}"] += 1
        self._counters["cache_eviction_total"] += 1
        
        logger.debug(f"Cache eviction: {layer}:{reason}")
    
    def start_timer(self, operation_id: str):
        """Start timing an operation"""
        self._start_times[operation_id] = time.time()
    
    def end_timer(self, operation_id: str, operation: str, layer: str) -> float:
        """End timing and record latency"""
        if operation_id not in self._start_times:
            return 0.0
        
        start_time = self._start_times.pop(operation_id)
        latency_ms = (time.time() - start_time) * 1000
        
        self.record_latency(operation, layer, latency_ms)
        return latency_ms
    
    def get_hit_rate(self, layer: Optional[str] = None, time_window: int = 300) -> float:
        """Get cache hit rate for time window"""
        cutoff_time = time.time() - time_window
        
        # Count hits and misses in time window
        hits = sum(1 for h in self._recent_hits 
                  if h["timestamp"] > cutoff_time and 
                  (layer is None or h["layer"] == layer))
        
        misses = sum(1 for m in self._recent_misses 
                    if m["timestamp"] > cutoff_time and 
                    (layer is None or m["layer"] == layer))
        
        total = hits + misses
        return hits / total if total > 0 else 0.0
    
    def get_avg_latency(self, operation: Optional[str] = None, 
                       layer: Optional[str] = None, time_window: int = 300) -> float:
        """Get average latency for time window"""
        cutoff_time = time.time() - time_window
        
        latencies = [l for l in self._recent_latencies 
                    if l["timestamp"] > cutoff_time and
                    (operation is None or l["operation"] == operation) and
                    (layer is None or l["layer"] == layer)]
        
        return sum(l["latency_ms"] for l in latencies) / len(latencies) if latencies else 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        now = datetime.now()
        uptime = (now - self._last_reset).total_seconds()
        
        stats = {
            "uptime_seconds": uptime,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "hit_rates": {
                "overall": self.get_hit_rate(),
                "memory": self.get_hit_rate("memory"),
                "redis": self.get_hit_rate("redis"),
                "last_5min": self.get_hit_rate(time_window=300),
                "last_1min": self.get_hit_rate(time_window=60)
            },
            "latencies": {
                "overall_avg_ms": self.get_avg_latency(),
                "memory_avg_ms": self.get_avg_latency(layer="memory"),
                "redis_avg_ms": self.get_avg_latency(layer="redis"),
                "last_5min_avg_ms": self.get_avg_latency(time_window=300),
                "last_1min_avg_ms": self.get_avg_latency(time_window=60)
            }
        }
        
        # Add histogram percentiles
        for key, values in self._histograms.items():
            if values:
                sorted_values = sorted(values)
                n = len(sorted_values)
                stats[f"{key}_p50"] = sorted_values[int(n * 0.5)]
                stats[f"{key}_p95"] = sorted_values[int(n * 0.95)]
                stats[f"{key}_p99"] = sorted_values[int(n * 0.99)]
                stats[f"{key}_max"] = max(values)
                stats[f"{key}_min"] = min(values)
        
        return stats
    
    def reset(self):
        """Reset all metrics"""
        self._counters.clear()
        self._histograms.clear()
        self._gauges.clear()
        self._start_times.clear()
        self._recent_hits.clear()
        self._recent_misses.clear()
        self._recent_latencies.clear()
        self._last_reset = datetime.now()
        
        logger.info("Cache metrics reset")


class CorrelationTracker:
    """Track correlation IDs for request tracing"""
    
    def __init__(self):
        self._correlations = {}
        self._active_requests = {}
    
    def generate_correlation_id(self, request_id: Optional[str] = None) -> str:
        """Generate or extract correlation ID"""
        if request_id:
            return f"req-{request_id}"
        
        import uuid
        return f"req-{uuid.uuid4().hex[:8]}"
    
    def start_request(self, correlation_id: str, operation: str):
        """Start tracking request"""
        self._active_requests[correlation_id] = {
            "operation": operation,
            "start_time": time.time(),
            "events": []
        }
    
    def add_event(self, correlation_id: str, event: str, details: Optional[Dict] = None):
        """Add event to correlation"""
        if correlation_id in self._active_requests:
            self._active_requests[correlation_id]["events"].append({
                "event": event,
                "details": details or {},
                "timestamp": time.time()
            })
    
    def end_request(self, correlation_id: str) -> Optional[Dict]:
        """End request tracking and return summary"""
        if correlation_id not in self._active_requests:
            return None
        
        request_data = self._active_requests.pop(correlation_id)
        duration = time.time() - request_data["start_time"]
        
        return {
            "correlation_id": correlation_id,
            "operation": request_data["operation"],
            "duration_ms": duration * 1000,
            "events": request_data["events"]
        }


# Global instances
_metrics: Optional[CacheMetrics] = None
_correlation_tracker: Optional[CorrelationTracker] = None


def get_metrics() -> CacheMetrics:
    """Get global metrics instance"""
    global _metrics
    if _metrics is None:
        _metrics = CacheMetrics()
    return _metrics


def get_correlation_tracker() -> CorrelationTracker:
    """Get global correlation tracker instance"""
    global _correlation_tracker
    if _correlation_tracker is None:
        _correlation_tracker = CorrelationTracker()
    return _correlation_tracker


# Decorator for automatic metrics collection

def track_cache_operation(operation: str, layer: str = "auto"):
    """Decorator to automatically track cache operations"""
    
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            metrics = get_metrics()
            correlation_tracker = get_correlation_tracker()
            
            # Generate correlation ID
            correlation_id = correlation_tracker.generate_correlation_id()
            correlation_tracker.start_request(correlation_id, operation)
            
            # Start timing
            metrics.start_timer(correlation_id)
            
            try:
                # Execute function
                result = await func(*args, **kwargs)
                
                # Record success
                correlation_tracker.add_event(correlation_id, "operation_success")
                
                return result
                
            except Exception as e:
                # Record error
                error_type = type(e).__name__
                metrics.record_error(operation, layer, error_type)
                correlation_tracker.add_event(correlation_id, "operation_error", {"error": str(e)})
                
                raise
            
            finally:
                # End timing and tracking
                latency = metrics.end_timer(correlation_id, operation, layer)
                summary = correlation_tracker.end_request(correlation_id)
                
                # Log correlation if enabled
                if summary and get_cache_settings().cache_log_level == "DEBUG":
                    logger.debug(f"Cache operation completed: {summary}")
        
        return wrapper
    
    return decorator


# Structured logging utilities

def log_cache_event(event: str, details: Dict[str, Any], correlation_id: Optional[str] = None):
    """Log cache event with structured data"""
    
    log_data = {
        "event": event,
        "timestamp": datetime.now().isoformat(),
        "details": details
    }
    
    if correlation_id:
        log_data["correlation_id"] = correlation_id
    
    logger.info(json.dumps(log_data))


def log_cache_performance(operation: str, layer: str, latency_ms: float, 
                         hit: bool, key_pattern: str, correlation_id: Optional[str] = None):
    """Log cache performance data"""
    
    log_data = {
        "event": "cache_performance",
        "operation": operation,
        "layer": layer,
        "latency_ms": latency_ms,
        "hit": hit,
        "key_pattern": key_pattern,
        "timestamp": datetime.now().isoformat()
    }
    
    if correlation_id:
        log_data["correlation_id"] = correlation_id
    
    logger.info(json.dumps(log_data))
