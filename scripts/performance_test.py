#!/usr/bin/env python3
"""
Performance testing script for cache system
"""

import asyncio
import time
import statistics
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from src.core.cache import get_cache_manager
from src.core.settings import get_cache_settings


class PerformanceTest:
    """Performance testing for cache operations"""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
    
    async def test_cache_set(self, iterations: int = 1000) -> Dict[str, Any]:
        """Test cache set performance"""
        print(f"🧪 Testing cache SET performance ({iterations} iterations)...")
        
        cache_manager = await get_cache_manager()
        latencies = []
        
        start_time = time.time()
        
        for i in range(iterations):
            key = f"perf_test:set:{i}"
            value = {"test_data": f"value_{i}", "timestamp": time.time()}
            
            operation_start = time.time()
            await cache_manager.set(key, value, ttl=300)
            operation_end = time.time()
            
            latencies.append((operation_end - operation_start) * 1000)  # Convert to ms
        
        total_time = time.time() - start_time
        
        result = {
            "operation": "SET",
            "iterations": iterations,
            "total_time": total_time,
            "avg_latency_ms": statistics.mean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "p95_latency_ms": statistics.quantiles(latencies, n=20)[18],  # 95th percentile
            "p99_latency_ms": statistics.quantiles(latencies, n=100)[98],  # 99th percentile
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "ops_per_second": iterations / total_time
        }
        
        self.results.append(result)
        return result
    
    async def test_cache_get(self, iterations: int = 1000) -> Dict[str, Any]:
        """Test cache get performance"""
        print(f"🧪 Testing cache GET performance ({iterations} iterations)...")
        
        cache_manager = await get_cache_manager()
        latencies = []
        hits = 0
        misses = 0
        
        # Pre-populate cache
        for i in range(iterations):
            key = f"perf_test:get:{i}"
            value = {"test_data": f"value_{i}", "timestamp": time.time()}
            await cache_manager.set(key, value, ttl=300)
        
        start_time = time.time()
        
        for i in range(iterations):
            key = f"perf_test:get:{i}"
            
            operation_start = time.time()
            result = await cache_manager.get(key)
            operation_end = time.time()
            
            latencies.append((operation_end - operation_start) * 1000)
            
            if result is not None:
                hits += 1
            else:
                misses += 1
        
        total_time = time.time() - start_time
        
        result = {
            "operation": "GET",
            "iterations": iterations,
            "total_time": total_time,
            "hits": hits,
            "misses": misses,
            "hit_rate": hits / iterations,
            "avg_latency_ms": statistics.mean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "p95_latency_ms": statistics.quantiles(latencies, n=20)[18],
            "p99_latency_ms": statistics.quantiles(latencies, n=100)[98],
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "ops_per_second": iterations / total_time
        }
        
        self.results.append(result)
        return result
    
    async def test_mixed_operations(self, iterations: int = 1000) -> Dict[str, Any]:
        """Test mixed cache operations"""
        print(f"🧪 Testing MIXED operations performance ({iterations} iterations)...")
        
        cache_manager = await get_cache_manager()
        set_latencies = []
        get_latencies = []
        delete_latencies = []
        
        start_time = time.time()
        
        for i in range(iterations):
            key = f"perf_test:mixed:{i}"
            value = {"test_data": f"value_{i}", "timestamp": time.time()}
            
            # SET operation
            set_start = time.time()
            await cache_manager.set(key, value, ttl=300)
            set_latencies.append((time.time() - set_start) * 1000)
            
            # GET operation
            get_start = time.time()
            await cache_manager.get(key)
            get_latencies.append((time.time() - get_start) * 1000)
            
            # DELETE operation
            delete_start = time.time()
            await cache_manager.delete(key)
            delete_latencies.append((time.time() - delete_start) * 1000)
        
        total_time = time.time() - start_time
        
        result = {
            "operation": "MIXED",
            "iterations": iterations,
            "total_time": total_time,
            "set_avg_latency_ms": statistics.mean(set_latencies),
            "get_avg_latency_ms": statistics.mean(get_latencies),
            "delete_avg_latency_ms": statistics.mean(delete_latencies),
            "ops_per_second": (iterations * 3) / total_time  # 3 operations per iteration
        }
        
        self.results.append(result)
        return result
    
    async def test_concurrent_operations(self, iterations: int = 100, concurrency: int = 10) -> Dict[str, Any]:
        """Test concurrent cache operations"""
        print(f"🧪 Testing CONCURRENT operations ({iterations} iterations, {concurrency} concurrent)...")
        
        async def concurrent_operation(operation_id: int):
            cache_manager = await get_cache_manager()
            latencies = []
            
            for i in range(iterations // concurrency):
                key = f"perf_test:concurrent:{operation_id}:{i}"
                value = {"operation_id": operation_id, "iteration": i}
                
                start = time.time()
                await cache_manager.set(key, value, ttl=60)
                await cache_manager.get(key)
                await cache_manager.delete(key)
                end = time.time()
                
                latencies.append((end - start) * 1000)
            
            return latencies
        
        start_time = time.time()
        
        # Run concurrent operations
        tasks = [concurrent_operation(i) for i in range(concurrency)]
        all_latencies = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Flatten all latencies
        flat_latencies = [lat for sublist in all_latencies for lat in sublist]
        
        result = {
            "operation": "CONCURRENT",
            "iterations": iterations,
            "concurrency": concurrency,
            "total_time": total_time,
            "avg_latency_ms": statistics.mean(flat_latencies),
            "median_latency_ms": statistics.median(flat_latencies),
            "p95_latency_ms": statistics.quantiles(flat_latencies, n=20)[18],
            "ops_per_second": iterations / total_time
        }
        
        self.results.append(result)
        return result
    
    def print_results(self):
        """Print performance test results"""
        print("\n" + "="*80)
        print("📊 PERFORMANCE TEST RESULTS")
        print("="*80)
        
        for result in self.results:
            print(f"\n🔍 {result['operation']} Operation:")
            print(f"  Iterations: {result['iterations']}")
            print(f"  Total time: {result['total_time']:.3f}s")
            print(f"  Ops/second: {result['ops_per_second']:.2f}")
            
            if 'avg_latency_ms' in result:
                print(f"  Avg latency: {result['avg_latency_ms']:.2f}ms")
                print(f"  Median latency: {result['median_latency_ms']:.2f}ms")
                print(f"  P95 latency: {result['p95_latency_ms']:.2f}ms")
                print(f"  P99 latency: {result['p99_latency_ms']:.2f}ms")
            
            if 'hit_rate' in result:
                print(f"  Hit rate: {result['hit_rate']:.2%}")
            
            if 'set_avg_latency_ms' in result:
                print(f"  SET avg latency: {result['set_avg_latency_ms']:.2f}ms")
                print(f"  GET avg latency: {result['get_avg_latency_ms']:.2f}ms")
                print(f"  DELETE avg latency: {result['delete_avg_latency_ms']:.2f}ms")


async def main():
    """Main performance test function"""
    print("🚀 Starting cache performance tests...")
    
    settings = get_cache_settings()
    if not settings.cache_enabled:
        print("⚠️  Cache is disabled, performance tests will be limited")
    
    print(f"📊 Cache backend: {settings.cache_backend}")
    
    try:
        # Initialize cache
        cache_manager = await get_cache_manager()
        
        # Run performance tests
        perf_test = PerformanceTest()
        
        # Test cache SET performance
        await perf_test.test_cache_set(1000)
        
        # Test cache GET performance
        await perf_test.test_cache_get(1000)
        
        # Test mixed operations
        await perf_test.test_mixed_operations(500)
        
        # Test concurrent operations
        await perf_test.test_concurrent_operations(200, 5)
        
        # Print results
        perf_test.print_results()
        
        print("\n✅ Performance tests completed!")
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
