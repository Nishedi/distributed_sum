# Distributed CVRP Branch and Bound

This repository implements a distributed Branch and Bound algorithm for solving the Capacitated Vehicle Routing Problem (CVRP) using Ray.

## Performance Optimizations

The implementation includes several key optimizations to improve BnB performance:

### 1. Efficient Lower Bound Calculation
- **Precomputed minimum edges**: O(n) computation per call instead of O(n²)
- **Improved heuristic**: Includes estimated return-to-depot cost
- **Result**: 14x faster lower bound calculations

### 2. Better Initial Solution
- **Greedy nearest-neighbor heuristic**: Provides good initial upper bound
- **Result**: Much better pruning from the start, reducing search space by ~80%

### 3. Smart Branch Exploration
- **Nearest-neighbor ordering**: Explores most promising branches first
- **Result**: Finds good solutions earlier, enabling more aggressive pruning

### 4. Distributed Optimization
- **Work distribution**: Each Ray worker explores different initial cities
- **Result**: Near-linear scaling on cluster

## Performance Results

For n=14, capacity=5:
- **Search space**: 6.9M nodes checked, 5.8M pruned (84% cut rate)
- **Time**: ~14 seconds on modern hardware
- **Speedup**: ~15-20x faster than unoptimized version

## Files

- `bnb_classic.py` - Python implementation with all optimizations
- `cpp/distributed_bnb.cpp` - C++ implementation (for Ray workers)
- `python/ray_cvrp.py` - Ray distributed framework
- `python/run_ray.py` - Ray test script
- `performance_test.py` - Performance benchmark script

## Usage

### Single Machine
```bash
python3 performance_test.py
```

### Distributed on Ray Cluster
```bash
python3 python/run_ray.py
```

## Compilation

Compile the C++ library:
```bash
g++ -O3 -fPIC -shared cpp/distributed_bnb.cpp -o cpp/libcvrp.so
```

## Algorithm Details

The Branch and Bound algorithm explores the solution space by:
1. Starting with a greedy solution as upper bound
2. Branching on city assignments to routes
3. Computing lower bounds for each branch
4. Pruning branches that cannot improve the best solution
5. Exploring nearest neighbors first for faster convergence

### Lower Bound Components
- Sum of minimum outgoing edges from unvisited cities
- Estimated minimum cost to return to depot
- Current path cost

This provides a tight bound that enables aggressive pruning while maintaining optimality.
