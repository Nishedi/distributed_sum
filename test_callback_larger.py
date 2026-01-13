#!/usr/bin/env python3
"""
Test the callback mechanism with a larger problem to ensure callbacks are actually invoked.
"""

import ctypes
import numpy as np
import time

# Load the library
LIB_PATH = "./cpp/libcvrp.so"
lib = ctypes.CDLL(LIB_PATH)

# Define the callback type
BOUND_QUERY_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p)

# Set up function signatures
lib.solve_from_first_city_with_callback.argtypes = [
    ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    BOUND_QUERY_CALLBACK,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_double
]
lib.solve_from_first_city_with_callback.restype = ctypes.c_double

lib.solve_from_first_city.argtypes = [
    ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int
]
lib.solve_from_first_city.restype = ctypes.c_double

# Create a larger test problem
n = 12  # 12 cities should take much longer
C = 5
np.random.seed(42)
coords = np.random.rand(n, 2) * 1000
dist = np.zeros((n, n))

for i in range(n):
    for j in range(n):
        dist[i, j] = np.linalg.norm(coords[i] - coords[j])

# Convert to ctypes
c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
for i in range(n):
    row = (ctypes.c_double * n)(*dist[i])
    c_mat[i] = row

print(f"Testing with n={n} cities, C={C} capacity")
print("="*60)

# Test 1: Without callback (baseline)
print("\n=== Test 1: Without callback (baseline) ===")
start = time.time()
result1 = lib.solve_from_first_city(c_mat, n, C, 1, 1, 999999999)
elapsed1 = time.time() - start
print(f"Result: {result1:.2f}")
print(f"Time: {elapsed1:.4f}s")

# Test 2: With callback, very frequent synchronization
print("\n=== Test 2: With callback (frequent: 1000 iter, 0.1s) ===")
callback_called = [0]
best_bound = [999999999.0]

def query_bound_callback(user_data):
    callback_called[0] += 1
    # Simulate getting progressively better bounds
    best_bound[0] = max(best_bound[0] * 0.995, result1 * 1.05)
    return best_bound[0]

callback = BOUND_QUERY_CALLBACK(query_bound_callback)

start = time.time()
result2 = lib.solve_from_first_city_with_callback(
    c_mat, n, C, 1, 1, 999999999,
    callback, None, 1000, 0.1  # Check every 1000 iterations or 0.1 seconds
)
elapsed2 = time.time() - start
print(f"Result: {result2:.2f}")
print(f"Time: {elapsed2:.4f}s")
print(f"Callback invocations: {callback_called[0]}")
if callback_called[0] > 0:
    print("✓ Callback mechanism is working!")
else:
    print("⚠ Warning: Callback was not called")

# Test 3: With callback, less frequent synchronization
print("\n=== Test 3: With callback (normal: 10000 iter, 1.0s) ===")
callback_called[0] = 0
best_bound[0] = 999999999.0

start = time.time()
result3 = lib.solve_from_first_city_with_callback(
    c_mat, n, C, 2, 1, 999999999,
    callback, None, 10000, 1.0  # Default settings
)
elapsed3 = time.time() - start
print(f"Result: {result3:.2f}")
print(f"Time: {elapsed3:.4f}s")
print(f"Callback invocations: {callback_called[0]}")

print("\n" + "="*60)
print("Summary:")
print(f"  Without callback: {elapsed1:.4f}s")
print(f"  With frequent sync: {elapsed2:.4f}s ({callback_called[0]} calls)")
print(f"  With normal sync: {elapsed3:.4f}s")
print("="*60)
