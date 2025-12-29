#!/usr/bin/env python3
"""
Performance test script to demonstrate BnB optimizations
Compares performance with different problem sizes
"""

import math
import random
import time
from bnb_classic import *

def run_performance_test():
    """Run performance tests on various problem sizes"""
    
    print("=" * 70)
    print("CVRP Branch and Bound - Performance Test")
    print("=" * 70)
    print()
    
    random.seed(42)
    test_sizes = [8, 9, 10, 11, 12, 13, 14]
    capacity = 5
    
    print(f"{'n':<5} {'Time(s)':<10} {'Checks':<12} {'Cuts':<12} {'Cut%':<8} {'Greedy':<10} {'Optimal':<10}")
    print("-" * 70)
    
    for n in test_sizes:
        # Generate coordinates
        coords = [(random.randint(0, 100), random.randint(0, 100)) for _ in range(n)]
        dist = [[0]*n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    dist[i][j] = math.sqrt((coords[i][0] - coords[j][0])**2 + 
                                          (coords[i][1] - coords[j][1])**2)
        
        # Run BnB with all optimizations
        solver = CVRP_BnB(dist, capacity=capacity, use_greedy_init=True)
        greedy_cost = solver.best_cost
        
        start_time = time.time()
        solver.branch_and_bound(cutting=True)
        elapsed = time.time() - start_time
        
        cut_percent = (solver.cut / solver.checks * 100) if solver.checks > 0 else 0
        
        print(f"{n:<5} {elapsed:<10.4f} {solver.checks:<12} {solver.cut:<12} "
              f"{cut_percent:<8.1f} {greedy_cost:<10.2f} {solver.best_cost:<10.2f}")
    
    print("-" * 70)
    print()
    print("Optimizations applied:")
    print("  1. Precomputed minimum edges (O(n) lower bound instead of O(n²))")
    print("  2. Improved lower bound with return-to-depot estimation")
    print("  3. Greedy nearest-neighbor initial solution")
    print("  4. Sorted branch exploration (nearest cities first)")
    print()

if __name__ == "__main__":
    run_performance_test()
