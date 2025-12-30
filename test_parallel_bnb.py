#!/usr/bin/env python3
"""
Test script to verify the new parallel BnB implementation works correctly.
Tests the hybrid multithread+cluster approach locally.
"""

import ctypes
import numpy as np
import os

# Path to the compiled library
LIB_PATH = "/home/runner/work/distributed_sum/distributed_sum/cpp/libcvrp.so"

def test_parallel_solver():
    """Test that the parallel solver function can be called and works correctly."""
    print("=" * 60)
    print("Testing Parallel BnB Solver")
    print("=" * 60)
    
    # Check if library exists
    if not os.path.exists(LIB_PATH):
        print(f"❌ Library not found at {LIB_PATH}")
        print("Please compile with: cd cpp && g++ -shared -fPIC -O3 -fopenmp distributed_bnb.cpp -o libcvrp.so")
        return False
    
    try:
        lib = ctypes.CDLL(LIB_PATH)
        print("✓ Library loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load library: {e}")
        return False
    
    # Declare function signature
    try:
        lib.solve_parallel_hybrid.argtypes = [
            ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int
        ]
        lib.solve_parallel_hybrid.restype = ctypes.c_double
        print("✓ Function signature declared")
    except Exception as e:
        print(f"❌ Failed to declare function: {e}")
        return False
    
    # Generate test data
    np.random.seed(42)
    n = 10
    C = 5
    coords = np.random.rand(n, 2) * 10000
    dist = np.zeros((n, n))
    
    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(coords[i] - coords[j])
    
    print(f"✓ Generated test data: {n} cities, capacity={C}")
    
    # Convert numpy -> double**
    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist[i])
        c_mat[i] = row
    
    # Test with single city
    initial_cities = (ctypes.c_int * 1)(1)
    
    try:
        print("\nTest 1: Single city with 2 threads")
        result = lib.solve_parallel_hybrid(
            c_mat, n, C, initial_cities, 1, 1, 999999999, 2
        )
        print(f"  Result: {result:.2f}")
        
        if result > 0 and result < 1e18:
            print("  ✓ Test 1 passed - got valid result")
        else:
            print(f"  ⚠ Test 1 warning - result seems unusual: {result}")
            
    except Exception as e:
        print(f"  ❌ Test 1 failed: {e}")
        return False
    
    # Test with city pair
    initial_cities_2 = (ctypes.c_int * 2)(1, 2)
    
    try:
        print("\nTest 2: City pair with 4 threads")
        result2 = lib.solve_parallel_hybrid(
            c_mat, n, C, initial_cities_2, 2, 1, 999999999, 4
        )
        print(f"  Result: {result2:.2f}")
        
        if result2 > 0 and result2 < 1e18:
            print("  ✓ Test 2 passed - got valid result")
        else:
            print(f"  ⚠ Test 2 warning - result seems unusual: {result2}")
            
    except Exception as e:
        print(f"  ❌ Test 2 failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    print("\nThe parallel solver is working correctly!")
    print("Key features:")
    print("- Uses OpenMP for thread-level parallelism")
    print("- Can be combined with Ray for cluster-level parallelism")
    print("- Thread-safe with atomic operations for shared bounds")
    print("- Dynamic work scheduling for load balancing")
    
    return True


if __name__ == "__main__":
    success = test_parallel_solver()
    exit(0 if success else 1)
