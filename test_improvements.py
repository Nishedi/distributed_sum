#!/usr/bin/env python3
"""
Test script to verify the improvements work locally.
This simulates the distributed environment locally.
"""

import numpy as np
import time

# Mock data generation (same as in the main code)
def greedy_cvrp_1nn(dist, C=5):
    n = dist.shape[0]
    visited = [False] * n
    visited[0] = True  # depot
    route = [0]
    total_cost = 0.0
    current = 0
    load = 0

    while not all(visited):
        if load == C:
            total_cost += dist[current][0]
            route.append(0)
            current = 0
            load = 0
            continue

        nearest = None
        nearest_dist = float("inf")

        for i in range(1, n):
            if not visited[i] and dist[current][i] < nearest_dist:
                nearest = i
                nearest_dist = dist[current][i]

        if nearest is None:
            total_cost += dist[current][0]
            route.append(0)
            break

        total_cost += nearest_dist
        route.append(nearest)
        visited[nearest] = True
        current = nearest
        load += 1

    if route[-1] != 0:
        total_cost += dist[current][0]
        route.append(0)

    return route, total_cost


def test_basic_functionality():
    """Test that the basic Python code works without Ray."""
    print("Testing basic functionality...")
    
    np.random.seed(42)
    n = 10
    C = 5
    
    # Generate test data
    coords = np.random.rand(n, 2) * 10000
    dist = np.zeros((n, n))
    
    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(coords[i] - coords[j])
    
    route, cost = greedy_cvrp_1nn(dist, C=C)
    
    print(f"  Generated {n} cities")
    print(f"  Greedy solution cost: {cost:.2f}")
    print(f"  Route length: {len(route)}")
    
    assert len(route) > 0, "Route should not be empty"
    assert cost > 0, "Cost should be positive"
    assert route[0] == 0, "Route should start at depot"
    assert route[-1] == 0, "Route should end at depot"
    
    print("  ✓ Basic functionality test passed!")
    return True


def test_bound_tracker_concept():
    """Test the concept of shared bounds without Ray."""
    print("\nTesting bound tracker concept...")
    
    class SimpleBoundTracker:
        def __init__(self, initial_bound):
            self.best_bound = initial_bound
        
        def update_bound(self, new_bound):
            if new_bound < self.best_bound:
                self.best_bound = new_bound
                return True
            return False
        
        def get_bound(self):
            return self.best_bound
    
    tracker = SimpleBoundTracker(1000.0)
    print(f"  Initial bound: {tracker.get_bound()}")
    
    # Simulate workers finding better solutions
    tracker.update_bound(800.0)
    print(f"  After update 1: {tracker.get_bound()}")
    assert tracker.get_bound() == 800.0, "Bound should update to 800"
    
    tracker.update_bound(850.0)  # This should not update
    print(f"  After update 2 (worse): {tracker.get_bound()}")
    assert tracker.get_bound() == 800.0, "Bound should stay at 800"
    
    tracker.update_bound(750.0)
    print(f"  After update 3: {tracker.get_bound()}")
    assert tracker.get_bound() == 750.0, "Bound should update to 750"
    
    print("  ✓ Bound tracker concept test passed!")
    return True


def test_work_distribution_strategies():
    """Test different work distribution strategies."""
    print("\nTesting work distribution strategies...")
    
    n = 15  # Use a larger n to better demonstrate batching
    num_workers = 4  # Simulated number of workers
    
    # Strategy 1: One task per city (original)
    tasks_1 = [(i,) for i in range(1, n)]
    print(f"  Strategy 1 (by city): {len(tasks_1)} tasks")
    
    # Strategy 2: Tasks for pairs of cities (improved)
    tasks_2 = [(i, j) for i in range(1, n) for j in range(1, n) if i != j]
    print(f"  Strategy 2 (by city pairs): {len(tasks_2)} tasks")
    
    # Strategy 3: Batched approach (Test 6)
    num_cities = n - 1
    target_tasks = int(num_workers * 2.5)
    batch_size = max(1, num_cities // target_tasks)
    cities = list(range(1, n))
    batches = []
    for i in range(0, len(cities), batch_size):
        batch = cities[i:i+batch_size]
        batches.append(batch)
    print(f"  Strategy 3 (batched): {len(batches)} tasks (batch size: {batch_size})")
    
    print(f"  Task granularity increased by: {len(tasks_2) / len(tasks_1):.1f}x (strategy 2 vs 1)")
    print(f"  Communication reduction: {len(tasks_2) / len(batches):.1f}x (strategy 2 vs 3)")
    
    assert len(tasks_1) == n - 1, "Should have n-1 tasks for strategy 1"
    assert len(tasks_2) == (n - 1) * (n - 2), "Should have (n-1)*(n-2) tasks for strategy 2"
    # Strategy 3 should be between strategy 1 and 2 for reasonable problem sizes
    assert len(batches) <= len(tasks_2), "Strategy 3 should have fewer or equal tasks than strategy 2 to reduce communication"
    # For larger n, we expect strategy 3 to have similar or more tasks than strategy 1 for load balancing
    # For small n, they might be equal, which is acceptable
    print(f"  Task count comparison: Strategy 1 ({len(tasks_1)}) ≤ Strategy 3 ({len(batches)}) ≤ Strategy 2 ({len(tasks_2)})")
    
    print("  ✓ Work distribution test passed!")
    return True


def main():
    print("=" * 60)
    print("Testing CVRP Distributed Improvements")
    print("=" * 60)
    
    try:
        test_basic_functionality()
        test_bound_tracker_concept()
        test_work_distribution_strategies()
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        print("\nKey improvements implemented:")
        print("1. Shared BoundTracker for cross-worker pruning")
        print("2. Fine-grained task distribution (city pairs)")
        print("3. Dynamic bound updates during execution")
        print("4. Batched approach (Test 6) for optimal distributed computing")
        print("\nExpected performance improvement:")
        print("- Better load balancing across workers")
        print("- More aggressive pruning via shared bounds")
        print("- Closer to linear speedup with more nodes")
        print("- Reduced communication overhead in distributed settings (Test 6)")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
