#!/usr/bin/env python3
"""
Comparison script: Classic BnB vs Multiprocessing
Shows the speedup achieved by multiprocessing approach
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import time
import numpy as np
from multiprocessing import cpu_count

# Import implementations
from bnb_classic import CVRP_BnB, distance_matrix
from python.multiprocessing_cvrp import run_distributed_bnb_mp
from python.greedy import greedy_cvrp_1nn


def compare_approaches(n=10, C=5):
    """Compare classic BnB with multiprocessing approach"""
    print("=" * 70)
    print(f"COMPARISON: Classic BnB vs Multiprocessing")
    print(f"Problem size: n={n}, C={C}")
    print(f"Available CPU cores: {cpu_count()}")
    print("=" * 70)
    print()
    
    # Generate test data with fixed seed
    np.random.seed(42)
    coords = [(np.random.randint(0, 10000), np.random.randint(0, 10000)) for _ in range(n)]
    dist_list = distance_matrix(coords)
    
    # Convert to numpy for multiprocessing
    dist_np = np.array(dist_list)
    
    # Get greedy solution
    print("Computing greedy solution...")
    route, greedy_cost = greedy_cvrp_1nn(dist_np, C=C)
    print(f"Greedy solution cost: {greedy_cost:.2f}")
    print()
    
    # Test 1: Classic BnB (sequential)
    print("Test 1: Classic Sequential BnB")
    print("-" * 70)
    solver = CVRP_BnB(dist_list, capacity=C)
    start_time = time.time()
    solver.branch_and_bound()
    classic_time = time.time() - start_time
    classic_cost = solver.best_cost
    print(f"Best cost: {classic_cost:.2f}")
    print(f"Time: {classic_time:.4f}s")
    print(f"Checks: {solver.checks}, Cuts: {solver.cut}")
    print()
    
    # Test 2: Multiprocessing BnB (coarse-grained)
    print("Test 2: Multiprocessing BnB - Coarse-grained")
    print("-" * 70)
    start_time = time.time()
    mp_cost_coarse = run_distributed_bnb_mp(n=n, C=C, BnB=1, bound_value=int(greedy_cost), 
                                             use_pairs=False, num_workers=cpu_count())
    mp_time_coarse = time.time() - start_time
    print(f"Best cost: {mp_cost_coarse:.2f}")
    print(f"Time: {mp_time_coarse:.4f}s")
    print(f"Speedup: {classic_time / mp_time_coarse:.2f}x")
    print()
    
    # Test 3: Multiprocessing BnB (fine-grained)
    print("Test 3: Multiprocessing BnB - Fine-grained")
    print("-" * 70)
    start_time = time.time()
    mp_cost_fine = run_distributed_bnb_mp(n=n, C=C, BnB=1, bound_value=int(greedy_cost), 
                                           use_pairs=True, num_workers=cpu_count())
    mp_time_fine = time.time() - start_time
    print(f"Best cost: {mp_cost_fine:.2f}")
    print(f"Time: {mp_time_fine:.4f}s")
    print(f"Speedup: {classic_time / mp_time_fine:.2f}x")
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Approach':<40} {'Time (s)':<12} {'Speedup':<10} {'Cost':<12}")
    print("-" * 70)
    print(f"{'Classic BnB (sequential)':<40} {classic_time:<12.4f} {'1.00x':<10} {classic_cost:<12.2f}")
    print(f"{'Multiprocessing (coarse-grained)':<40} {mp_time_coarse:<12.4f} {classic_time/mp_time_coarse:<10.2f}x {mp_cost_coarse:<12.2f}")
    print(f"{'Multiprocessing (fine-grained)':<40} {mp_time_fine:<12.4f} {classic_time/mp_time_fine:<10.2f}x {mp_cost_fine:<12.2f}")
    print("=" * 70)
    print()
    
    # Verify correctness
    best_cost = min(classic_cost, mp_cost_coarse, mp_cost_fine)
    tolerance = 0.01
    if abs(classic_cost - best_cost) > tolerance or \
       abs(mp_cost_coarse - best_cost) > tolerance or \
       abs(mp_cost_fine - best_cost) > tolerance:
        print("⚠️  Warning: Results differ between approaches!")
        print(f"   Classic: {classic_cost:.2f}")
        print(f"   MP Coarse: {mp_cost_coarse:.2f}")
        print(f"   MP Fine: {mp_cost_fine:.2f}")
    else:
        print("✅ All approaches found the same optimal solution!")
    
    return {
        'classic_time': classic_time,
        'mp_coarse_time': mp_time_coarse,
        'mp_fine_time': mp_time_fine,
        'classic_cost': classic_cost,
        'mp_coarse_cost': mp_cost_coarse,
        'mp_fine_cost': mp_cost_fine
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
    else:
        n = 10
    
    if len(sys.argv) > 2:
        C = int(sys.argv[2])
    else:
        C = 5
    
    try:
        results = compare_approaches(n, C)
    except Exception as e:
        print(f"\n❌ Comparison failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
