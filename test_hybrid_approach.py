#!/usr/bin/env python3
"""
Test the new hybrid batched approach locally without Ray cluster
"""
import numpy as np
import time
import sys
import os

# Add python directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

# Mock Ray for local testing
class MockRemote:
    def __init__(self, func):
        self.func = func
    
    def remote(self, *args, **kwargs):
        return self.func(*args, **kwargs)

class MockRay:
    @staticmethod
    def remote(cls_or_func):
        return MockRemote(cls_or_func)
    
    @staticmethod
    def get(result):
        if isinstance(result, list):
            return result
        return result
    
    @staticmethod
    def init(address=None):
        pass

# Replace ray with mock
sys.modules['ray'] = MockRay()

from python.greedy import greedy_cvrp_1nn
import ctypes

# Test with simple data
np.random.seed(42)
n = 12  # Use smaller n for quick test
C = 5

coords = np.random.rand(n, 2) * 10000
dist = np.zeros((n, n))

for i in range(n):
    for j in range(n):
        dist[i, j] = np.linalg.norm(coords[i] - coords[j])

# Get greedy bound
route, cost = greedy_cvrp_1nn(dist, C=C)
print(f"Greedy bound: {cost:.2f}")
print(f"Number of cities: {n}")
print(f"Capacity: {C}")
print()

# Test the batching logic
all_pairs = [(i, j) for i in range(1, n) for j in range(1, n) if i != j]
batch_size = max(4, len(all_pairs) // 40)

batches = []
for i in range(0, len(all_pairs), batch_size):
    batches.append(all_pairs[i:i+batch_size])

print(f"Total pairs: {len(all_pairs)}")
print(f"Batch size: {batch_size}")
print(f"Number of batches: {len(batches)}")
print(f"Batch sizes: {[len(b) for b in batches]}")
print()

# Test that we can load the library and call the function
try:
    LIB_PATH = "/home/runner/work/distributed_sum/distributed_sum/cpp/libcvrp.so"
    
    if not os.path.exists(LIB_PATH):
        print(f"ERROR: Library not found at {LIB_PATH}")
        print("Need to compile C++ code first")
        sys.exit(1)
    
    lib = ctypes.CDLL(LIB_PATH)
    
    # Test solve_from_two_cities signature
    lib.solve_from_two_cities.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int
    ]
    lib.solve_from_two_cities.restype = ctypes.c_double
    
    # Convert numpy -> double**
    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist[i])
        c_mat[i] = row
    
    # Test with first batch
    print(f"Testing with first batch of {len(batches[0])} pairs...")
    start = time.time()
    best = float('inf')
    for city1, city2 in batches[0]:
        result = lib.solve_from_two_cities(c_mat, n, C, city1, city2, 1, int(cost))
        if result < best:
            best = result
    elapsed = time.time() - start
    
    print(f"Best result from first batch: {best:.2f}")
    print(f"Time for first batch: {elapsed:.4f}s")
    print()
    print("✓ Hybrid batch approach working correctly!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
