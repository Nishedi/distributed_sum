#!/usr/bin/env python3
"""
Test script to verify C++ upper bound synchronization with host.
This script tests the new synchronization feature in a simple scenario.
"""

import ray
import numpy as np
import time
from python.ray_cvrp import solve_city, solve_city_pair, BoundTracker
from python.greedy import greedy_cvrp_1nn

# Initialize Ray
ray.init(address="auto", ignore_reinit_error=True)

# Create a small test problem
n = 12  # Number of cities
C = 5   # Vehicle capacity

np.random.seed(42)
coords = np.random.rand(n, 2) * 10000
dist = np.zeros((n, n))

for i in range(n):
    for j in range(n):
        dist[i, j] = np.linalg.norm(coords[i] - coords[j])

# Get initial bound from greedy
route, cost = greedy_cvrp_1nn(dist, C=C)
print(f"Greedy solution cost: {cost:.2f}")
print(f"Number of cities: {n}")
print(f"Vehicle capacity: {C}")
print()

# Test 1: Without synchronization (for baseline)
print("=== Test 1: Without synchronization (baseline) ===")
start_time = time.time()
futures = [solve_city.remote(dist, C, i, 1, 999999999) for i in range(1, min(4, n))]
results = ray.get(futures)
elapsed = time.time() - start_time
print(f"Best cost: {min(results):.2f}")
print(f"Time: {elapsed:.4f}s")
print()

# Test 2: With synchronization (sync every 5000 iterations, 0.5 seconds)
print("=== Test 2: With synchronization (5000 iter, 0.5s) ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(int(cost))
futures = [solve_city.remote(dist, C, i, 1, int(cost), bound_tracker, 5000, 0.5) for i in range(1, min(4, n))]
results = ray.get(futures)
elapsed = time.time() - start_time
final_bound = ray.get(bound_tracker.get_bound.remote())
print(f"Best cost: {min(results):.2f}")
print(f"Final bound: {final_bound:.2f}")
print(f"Time: {elapsed:.4f}s")
print()

# Test 3: With very frequent synchronization (1000 iter, 0.1s) - should still work but be slower
print("=== Test 3: With frequent synchronization (1000 iter, 0.1s) ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(int(cost))
futures = [solve_city.remote(dist, C, i, 1, int(cost), bound_tracker, 1000, 0.1) for i in range(1, min(4, n))]
results = ray.get(futures)
elapsed = time.time() - start_time
final_bound = ray.get(bound_tracker.get_bound.remote())
print(f"Best cost: {min(results):.2f}")
print(f"Final bound: {final_bound:.2f}")
print(f"Time: {elapsed:.4f}s")
print()

# Test 4: City pairs with synchronization
print("=== Test 4: City pairs with synchronization (10000 iter, 1.0s) ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(int(cost))
futures = [solve_city_pair.remote(dist, C, i, j, 1, int(cost), bound_tracker, 10000, 1.0)
           for i in range(1, min(4, n)) for j in range(1, min(4, n)) if i != j]
results = ray.get(futures)
elapsed = time.time() - start_time
final_bound = ray.get(bound_tracker.get_bound.remote())
print(f"Best cost: {min(results):.2f}")
print(f"Final bound: {final_bound:.2f}")
print(f"Time: {elapsed:.4f}s")
print(f"Number of tasks: {len(futures)}")
print()

print("=== All tests completed successfully! ===")

ray.shutdown()
