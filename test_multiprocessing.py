#!/usr/bin/env python3
"""
Test script for multiprocessing CVRP implementation
Tests basic functionality without requiring a full run
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

import numpy as np
from python.multiprocessing_cvrp import run_distributed_bnb_mp
from python.greedy import greedy_cvrp_1nn


def test_multiprocessing_small():
    """Test with a small problem (n=8) to verify correctness"""
    print("=== Testing Multiprocessing CVRP with n=8 ===")
    
    # Use fixed seed for reproducibility
    np.random.seed(42)
    n = 8
    C = 5
    
    # Generate test data
    coords = np.random.rand(n, 2) * 1000
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(coords[i] - coords[j])
    
    # Get greedy solution
    route, greedy_cost = greedy_cvrp_1nn(dist, C=C)
    print(f"Greedy solution cost: {greedy_cost:.2f}")
    
    # Test coarse-grained multiprocessing with greedy bound
    print("\nTest 1: Coarse-grained (single cities) with greedy bound")
    result1 = run_distributed_bnb_mp(n=n, C=C, BnB=1, bound_value=int(greedy_cost), 
                                      use_pairs=False, num_workers=2)
    print(f"Result: {result1:.2f}")
    
    # Test fine-grained multiprocessing
    print("\nTest 2: Fine-grained (city pairs)")
    result2 = run_distributed_bnb_mp(n=n, C=C, BnB=1, bound_value=int(greedy_cost), 
                                      use_pairs=True, num_workers=2)
    print(f"Result: {result2:.2f}")
    
    # Verify results are valid (should be better than or equal to greedy)
    assert result1 <= greedy_cost, f"Result1 {result1} should be <= greedy {greedy_cost}"
    assert result2 <= greedy_cost, f"Result2 {result2} should be <= greedy {greedy_cost}"
    
    # Results should be the same (both should find optimal)
    assert abs(result1 - result2) < 0.01, f"Results should match: {result1} vs {result2}"
    
    print("\n✅ All tests passed!")
    print(f"Multiprocessing found solution: {result1:.2f}")
    print(f"Greedy solution: {greedy_cost:.2f}")
    print(f"Improvement: {(greedy_cost - result1) / greedy_cost * 100:.1f}%")
    
    return True


if __name__ == "__main__":
    try:
        test_multiprocessing_small()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
