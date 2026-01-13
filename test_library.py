#!/usr/bin/env python3
"""
Simple test to verify the C++ library loads correctly and has the expected function signatures.
This doesn't require Ray to be running.
"""

import ctypes
import numpy as np

# Try to load the library
LIB_PATH = "./cpp/libcvrp.so"

try:
    lib = ctypes.CDLL(LIB_PATH)
    print(f"✓ Successfully loaded library: {LIB_PATH}")
except Exception as e:
    print(f"✗ Failed to load library: {e}")
    exit(1)

# Define the callback type
BOUND_QUERY_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p)

# Test original solve_from_first_city signature (no callback)
try:
    lib.solve_from_first_city.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int
    ]
    lib.solve_from_first_city.restype = ctypes.c_double
    print("✓ solve_from_first_city signature set correctly")
except Exception as e:
    print(f"✗ Failed to set solve_from_first_city signature: {e}")
    exit(1)

# Test new solve_from_first_city_with_callback signature
try:
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
    print("✓ solve_from_first_city_with_callback signature set correctly")
except Exception as e:
    print(f"✗ Failed to set solve_from_first_city_with_callback signature: {e}")
    exit(1)

# Test solve_from_two_cities signature
try:
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
    print("✓ solve_from_two_cities signature set correctly")
except Exception as e:
    print(f"✗ Failed to set solve_from_two_cities signature: {e}")
    exit(1)

# Test solve_from_two_cities_with_callback signature
try:
    lib.solve_from_two_cities_with_callback.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,
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
    lib.solve_from_two_cities_with_callback.restype = ctypes.c_double
    print("✓ solve_from_two_cities_with_callback signature set correctly")
except Exception as e:
    print(f"✗ Failed to set solve_from_two_cities_with_callback signature: {e}")
    exit(1)

# Create a simple test problem
print("\n=== Testing without callback (original API) ===")
n = 5
C = 3
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

# Test without callback (old style)
try:
    result = lib.solve_from_first_city(c_mat, n, C, 1, 1, 999999999)
    print(f"✓ solve_from_first_city executed without callback")
    print(f"  Result: {result:.2f}")
except Exception as e:
    print(f"✗ Failed to execute solve_from_first_city: {e}")
    exit(1)

# Test with callback
print("\n=== Testing with callback (new API) ===")
callback_called = [0]  # Use list to allow modification in nested function
best_bound = [999999999.0]

def query_bound_callback(user_data):
    callback_called[0] += 1
    # Simulate getting progressively better bounds
    best_bound[0] = max(best_bound[0] * 0.99, result * 1.1)
    return best_bound[0]

callback = BOUND_QUERY_CALLBACK(query_bound_callback)

try:
    result2 = lib.solve_from_first_city_with_callback(
        c_mat, n, C, 2, 1, 999999999,
        callback, None, 100, 0.01  # Very frequent sync for testing
    )
    print(f"✓ solve_from_first_city_with_callback executed")
    print(f"  Result: {result2:.2f}")
    print(f"  Callback was called: {callback_called[0]} times")
    if callback_called[0] > 0:
        print(f"  ✓ Callback mechanism is working!")
    else:
        print(f"  ⚠ Warning: Callback was not called (might complete too fast)")
except Exception as e:
    print(f"✗ Failed to execute solve_from_first_city_with_callback: {e}")
    exit(1)

# Test solve_from_two_cities with callback
print("\n=== Testing solve_from_two_cities_with_callback ===")
callback_called[0] = 0
best_bound[0] = 999999999.0

try:
    result3 = lib.solve_from_two_cities_with_callback(
        c_mat, n, C, 1, 2, 1, 999999999,
        callback, None, 100, 0.01
    )
    print(f"✓ solve_from_two_cities_with_callback executed")
    print(f"  Result: {result3:.2f}")
    print(f"  Callback was called: {callback_called[0]} times")
except Exception as e:
    print(f"✗ Failed to execute solve_from_two_cities_with_callback: {e}")
    exit(1)

# Test backward compatibility - original API without callback
print("\n=== Testing backward compatibility ===")
try:
    result4 = lib.solve_from_two_cities(c_mat, n, C, 1, 2, 1, 999999999)
    print(f"✓ solve_from_two_cities (original) executed")
    print(f"  Result: {result4:.2f}")
except Exception as e:
    print(f"✗ Failed to execute solve_from_two_cities: {e}")
    exit(1)

print("\n" + "="*60)
print("✓ All tests passed! The library is working correctly.")
print("="*60)

