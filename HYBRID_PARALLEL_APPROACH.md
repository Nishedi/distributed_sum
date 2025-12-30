# Hybrid Multithread+Cluster BnB Algorithm

## Overview

This document describes the new hybrid Branch-and-Bound algorithm that combines:
- **Cluster-level parallelism** (Ray distributed computing)
- **Thread-level parallelism** (OpenMP multithreading)
- **Fine-grained task distribution** (city pairs)
- **Shared bound tracking** (cross-worker communication)

## Problem Being Solved

The previous implementations showed good improvements but still had limitations:

### Results from test_one_vs_all_16_sorted.csv (n=16):

| Approach | Single Thread | Single Node MT | Cluster ST | Cluster MT |
|----------|--------------|----------------|------------|-----------|
| Test 1 (Basic BnB) | 2598s | 522s | 363s | 246s |
| Test 5 (Fine-grained) | 432s | 151s | 99s | **Best: 99s** |

**Key Observation**: Even with cluster+multithread, we're not achieving optimal speedup because:
1. Ray workers don't utilize available CPU cores within each node
2. Fine-grained tasks are sequential within each worker
3. No thread-level parallelism to complement cluster-level distribution

## New Approach: Hybrid Parallelism

### Architecture

```
Cluster Level (Ray)
├── Worker Node 1
│   └── Thread Pool (OpenMP)
│       ├── Thread 1 → Process subtask A
│       ├── Thread 2 → Process subtask B
│       ├── Thread 3 → Process subtask C
│       └── Thread 4 → Process subtask D
├── Worker Node 2
│   └── Thread Pool (OpenMP)
│       ├── Thread 1 → Process subtask E
│       └── ...
└── Worker Node N
    └── Thread Pool (OpenMP)
```

### Key Features

1. **OpenMP Parallelism** (C++ level)
   - Each Ray task spawns multiple threads
   - Dynamic work scheduling within threads
   - Thread-safe shared bound updates using `#pragma omp critical`
   - Automatic load balancing via `schedule(dynamic, 1)`

2. **Configurable Thread Count**
   - Test 6: 4 threads per task (coarse-grained)
   - Test 7: 2 threads per task (fine-grained)
   - Adaptive based on task granularity

3. **Shared Bound Optimization**
   - Global bound tracked by Ray actor
   - Local thread-level bound sharing within workers
   - Periodic synchronization for best performance

## Implementation Details

### C++ (distributed_bnb.cpp)

Added new function `solve_parallel_hybrid`:

```cpp
double solve_parallel_hybrid(double** dist, int n, int C, 
                             int* initial_cities, int initial_count,
                             int cutting, int bound_value, int num_threads)
```

Key aspects:
- Uses `#pragma omp parallel` for thread pool
- Dynamic scheduling: `#pragma omp for schedule(dynamic, 1)`
- Critical sections for bound updates: `#pragma omp critical`
- Thread-local solver instances to avoid contention

### Python (ray_cvrp.py)

Added two new remote functions:

1. `solve_city_parallel`: Single city start with multithreading
2. `solve_city_pair_parallel`: City pair start with multithreading

Both support configurable thread counts via `num_threads` parameter.

### Test Scenarios (run_ray.py)

**Test 6: Hybrid with coarse-grained tasks**
```python
futures = [solve_city_parallel.remote(dist, C, i, 1, int(cost), 
                                       bound_tracker, num_threads=4) 
           for i in range(1, n)]
```
- n-1 Ray tasks
- 4 threads per task
- Best for: Small to medium clusters

**Test 7: Hybrid with fine-grained tasks**
```python
futures = [solve_city_pair_parallel.remote(dist, C, i, j, 1, int(cost), 
                                            bound_tracker, num_threads=2) 
           for i in range(1, n) for j in range(1, n) if i != j]
```
- (n-1)×(n-2) Ray tasks
- 2 threads per task
- Best for: Large clusters with multicore nodes

## Expected Performance

### Theoretical Speedup

For a cluster with:
- 9 nodes
- 8 cores per node
- n=16 cities

**Previous Best (Test 5):**
- Tasks: 15×14 = 210 tasks
- Cores used per node: 1
- Total parallel work: 210 task-units
- Time: ~99s

**New Approach (Test 6):**
- Tasks: 15 tasks
- Cores per task: 4
- Total parallel work: 15×4 = 60 thread-units
- Expected speedup: 1.5-2x → ~50-65s

**New Approach (Test 7):**
- Tasks: 210 tasks
- Cores per task: 2
- Total parallel work: 210×2 = 420 thread-units
- Expected speedup: 2-2.5x → ~40-50s

### Why This Works Better

1. **Better CPU Utilization**
   - Previous: 1 CPU core per Ray worker
   - New: Multiple cores per Ray worker
   - Result: Higher hardware utilization

2. **Reduced Communication Overhead**
   - Thread-level sharing is faster than inter-process sharing
   - Less Ray actor communication needed

3. **Adaptive Granularity**
   - Can tune threads vs tasks for optimal performance
   - Flexible for different cluster configurations

## Compilation

The library must be compiled with OpenMP support:

```bash
cd cpp
g++ -shared -fPIC -O3 -fopenmp distributed_bnb.cpp -o libcvrp.so
```

The `-fopenmp` flag is essential for multithreading support.

## Usage

### Basic Testing

```bash
# Test the implementation locally
python test_parallel_bnb.py

# Run all tests including new ones
python python/run_ray.py --n 16 --C 5
```

### Configuration Tips

1. **For multicore single node:**
   - Use Test 6 with threads = number of cores
   - Example: `num_threads=8` for 8-core machine

2. **For cluster with multicore nodes:**
   - Use Test 7 with threads = cores/2
   - Let Ray distribute many tasks across nodes
   - Let OpenMP use multiple cores per task

3. **For memory-constrained systems:**
   - Use Test 6 with fewer threads
   - Reduces memory overhead from many tasks

## Performance Tuning

### Thread Count Selection

```python
# Conservative (more tasks, fewer threads per task)
num_threads = 2  # Good for large clusters

# Balanced (medium tasks, medium threads)
num_threads = 4  # Good for most scenarios

# Aggressive (fewer tasks, more threads per task)
num_threads = 8  # Good for powerful single nodes
```

### Task Granularity

```python
# Coarse-grained (Test 6 style)
tasks = [(i,) for i in range(1, n)]  # n-1 tasks

# Fine-grained (Test 7 style)
tasks = [(i,j) for i in range(1,n) for j in range(1,n) if i!=j]  # (n-1)(n-2) tasks

# Ultra-fine-grained (experimental)
tasks = [(i,j,k) for i in range(1,n) for j in range(1,n) 
         for k in range(1,n) if i!=j!=k]  # Even more tasks
```

## Limitations

1. **OpenMP Availability**
   - Requires OpenMP support in compiler
   - May not work on all systems

2. **Memory Usage**
   - More threads = more memory per worker
   - Monitor with large problem sizes (n > 18)

3. **Optimal Thread Count**
   - Depends on hardware configuration
   - May need tuning for specific clusters

## Future Improvements

1. **Auto-tuning**: Automatically detect optimal thread count
2. **Adaptive switching**: Change granularity during execution
3. **NUMA awareness**: Pin threads to specific cores
4. **GPU acceleration**: Offload bound calculations to GPU
5. **Hierarchical parallelism**: 3-level (cluster/node/thread)

## Summary

The hybrid approach combines the best of both worlds:
- **Ray** handles cluster-level distribution and fault tolerance
- **OpenMP** handles thread-level parallelism within nodes
- **Result**: Better CPU utilization and faster execution times

This approach is particularly effective for:
- ✅ Clusters with multicore nodes
- ✅ Problems with irregular workloads
- ✅ Scenarios requiring both scalability and efficiency
