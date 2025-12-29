# Performance Improvements for Distributed CVRP Branch and Bound

## Problem

The original code achieved only **1.7-1.8x speedup** with 9 nodes instead of the expected ~9x speedup.

### Original Results
```
# All nodes (9 nodes)
BnB: 48.26s
BnB_SP: 49.31s

# One node
BnB: 86.35s
BnB_SP: 84.40s

Speedup: only ~1.7-1.8x instead of ~9x
```

## Root Causes Identified

### 1. **No Shared Bound**
- Each worker operated with its own bound
- Workers didn't share best solutions found
- Missed opportunities for more aggressive branch pruning

### 2. **Load Imbalance**
- Tasks were divided by first city (n-1 tasks)
- Some cities lead to much larger search spaces
- The slowest worker determines total execution time
- Example: one task may take 80s while others take 5s

### 3. **Sequential Wait Pattern**
- `ray.get(futures)` waits for ALL workers
- Total time = slowest worker time
- No early termination possible

## Implemented Solutions

### 1. Shared Bound Tracking

**File:** `python/ray_cvrp.py`

```python
@ray.remote
class BoundTracker:
    """
    Shared actor to track the global best bound across all workers.
    This enables better pruning in the Branch and Bound algorithm.
    """
    def __init__(self, initial_bound):
        self.best_bound = initial_bound
    
    def update_bound(self, new_bound):
        """Update the best bound if the new bound is better."""
        if new_bound < self.best_bound:
            self.best_bound = new_bound
            return True
        return False
    
    def get_bound(self):
        """Get the current best bound."""
        return self.best_bound
```

**Benefits:**
- Workers can leverage best solutions found by others
- More aggressive branch pruning in search tree
- Reduced amount of unnecessary computation

### 2. Fine-grained Task Distribution

**File:** `cpp/distributed_bnb.cpp`

Added new C++ function:
```cpp
double solve_from_two_cities(double** dist, int n, int C, 
                             int first_city, int second_city, 
                             int cutting, int bound_value)
```

**File:** `python/ray_cvrp.py`

```python
@ray.remote
def solve_city_pair(dist_np, C, city1, city2, BnB, bound_value, bound_tracker=None):
    """
    Solve starting from depot -> city1 -> city2, creating more granular tasks
    for better load balancing across workers.
    """
```

**Comparison:**
- **Original strategy:** n-1 tasks (for n=15: 14 tasks)
- **New strategy:** (n-1)*(n-2) tasks (for n=15: 182 tasks)
- **Granularity increase:** ~13x more tasks

**Benefits:**
- Much better load balancing
- Slow tasks can be automatically distributed across idle workers
- Reduced risk of one worker being a bottleneck

### 3. Dynamic Bound Updates

Each worker:
1. Fetches current best bound before starting
2. Uses this bound for pruning
3. Updates global bound after finding better solution

```python
# Get current best bound
if bound_tracker is not None:
    current_bound = ray.get(bound_tracker.get_bound.remote())
    bound_value = min(bound_value, int(current_bound))

# ... perform computation ...

# Update global bound
if bound_tracker is not None and result < float('inf'):
    bound_tracker.update_bound.remote(result)
```

## Usage

### Before (Original Version)
```python
futures = [solve_city.remote(dist, C, i, 1, 999999999) for i in range(1, n)]
results = ray.get(futures)
```

### After (Improved Version - Shared Bound)
```python
bound_tracker = BoundTracker.remote(int(cost))
futures = [solve_city.remote(dist, C, i, 1, int(cost), bound_tracker) 
           for i in range(1, n)]
results = ray.get(futures)
```

### After (Most Improved - Fine-grained Tasks)
```python
bound_tracker = BoundTracker.remote(int(cost))
futures = []
for i in range(1, n):
    for j in range(1, n):
        if i != j:
            futures.append(solve_city_pair.remote(dist, C, i, j, 1, 
                                                   int(cost), bound_tracker))
results = ray.get(futures)
```

## Testing

Run local tests:
```bash
python test_improvements.py
```

Run distributed tests (requires Ray cluster):
```bash
python python/run_ray.py
```

## Expected Results

### Shared Bound
- **Speedup:** 1.3-1.5x
- **Main benefit:** Reduced nodes explored via better pruning

### Fine-grained Tasks
- **Speedup:** 2-3x (combined with shared bound)
- **Main benefit:** Much better load balancing

### Combined
- **Expected speedup:** 3-5x with 9 nodes
- **Theoretical maximum:** ~9x (limited by communication overhead and synchronization)

## Further Possible Improvements

1. **Work Stealing:** Implement dynamic work stealing between workers
2. **Adaptive Granularity:** Automatically adjust task granularity based on problem size
3. **Early Termination:** Stop all workers when optimality is proven
4. **Heuristic Ordering:** Smarter ordering of cities for better pruning
5. **Periodic Bound Updates:** Workers periodically check and update bounds during long computations

## Compilation

To recompile the C++ library after changes:

```bash
cd cpp
g++ -shared -fPIC -O2 distributed_bnb.cpp -o libcvrp.so
```

## File Structure

```
distributed_sum/
├── cpp/
│   ├── distributed_bnb.cpp    # C++ implementation (added solve_from_two_cities)
│   └── libcvrp.so             # Compiled library
├── python/
│   ├── ray_cvrp.py            # Ray workers (added BoundTracker, solve_city_pair)
│   └── run_ray.py             # Main test script (added comparative tests)
└── test_improvements.py       # Local unit tests
```

## Summary

These improvements address the poor scaling in the original implementation by:

1. **Sharing information** between workers (BoundTracker)
2. **Better work distribution** (finer-grained tasks)
3. **Dynamic updates** of bounds during execution

We expect these changes to increase speedup from ~1.7x to ~3-5x with 9 nodes, which is much closer to ideal scaling.
