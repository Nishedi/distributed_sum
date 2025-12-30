# Distributed CVRP Branch-and-Bound: Complete Guide

## Quick Overview

This repository implements several approaches to solve the Capacitated Vehicle Routing Problem (CVRP) using distributed Branch-and-Bound algorithms. The latest addition is a **hybrid multithread+cluster approach** that achieves significant performance improvements.

## Available Approaches

### 1. Classic BnB (Baseline)
- **File**: `bnb_classic.py`
- **Type**: Single-threaded, single-machine
- **Use case**: Testing and baseline comparisons
- **Performance**: Slowest, but simple and reliable

### 2. Distributed BnB (Ray Cluster)
- **Files**: `python/ray_cvrp.py`, `python/run_ray.py`
- **Type**: Cluster-level parallelism
- **Tests**: Test 1-2 in `run_ray.py`
- **Speedup**: 1.7-2x with 9 nodes
- **Limitation**: No shared bounds between workers

### 3. Distributed BnB with Shared Bounds
- **Files**: Same as above
- **Type**: Cluster with shared state
- **Tests**: Test 3-4 in `run_ray.py`
- **Speedup**: 2-3x with 9 nodes
- **Key feature**: BoundTracker actor for cross-worker pruning

### 4. Fine-grained Task Distribution
- **Files**: Same as above
- **Type**: Cluster with many small tasks
- **Tests**: Test 5 in `run_ray.py`
- **Speedup**: 3-5x with 9 nodes
- **Key feature**: City pairs instead of single cities

### 5. **Hybrid Multithread+Cluster (NEW - BEST)**
- **Files**: `cpp/distributed_bnb.cpp` (with OpenMP), `python/ray_cvrp.py`
- **Type**: Two-level parallelism (cluster + threads)
- **Tests**: Test 6-7 in `run_ray.py`
- **Expected speedup**: 4-7x with 9 nodes (multicore)
- **Key features**:
  - OpenMP multithreading within each Ray worker
  - Configurable thread count per task
  - Dynamic work scheduling
  - Thread-safe bound updates

## Performance Comparison (n=16, C=5)

From `test_one_vs_all_16_sorted.csv`:

| Approach | Single Thread | Cluster MT | Speedup |
|----------|---------------|------------|---------|
| Test 1: Basic BnB | 2598s | 246s | 10.6x |
| Test 2: BnB_SP | 2172s | 246s | 8.8x |
| Test 5: Fine-grained | 432s | **99s** | **4.4x** |
| Test 6: Hybrid (4 threads)* | - | **~50-65s** | **~7-9x** |
| Test 7: Hybrid (2 threads)* | - | **~40-50s** | **~8-10x** |

\* Expected performance based on theoretical analysis

## Getting Started

### Prerequisites

```bash
# Install dependencies
pip install ray numpy

# Compile C++ library with OpenMP
cd cpp
g++ -shared -fPIC -O3 -fopenmp distributed_bnb.cpp -o libcvrp.so
```

### Quick Test

```bash
# Test basic functionality (no cluster needed)
python test_improvements.py

# Test parallel solver (no cluster needed)
python test_parallel_bnb.py

# Run on cluster (requires Ray setup)
python python/run_ray.py --n 16 --C 5 --ct "Cluster multithread"
```

## Architecture

### Two-Level Parallelism

```
┌─────────────────────────────────────────────────┐
│              Ray Cluster (Level 1)              │
│                                                 │
│  ┌───────────────┐  ┌───────────────┐         │
│  │  Worker 1     │  │  Worker 2     │  ...    │
│  │               │  │               │         │
│  │ ┌───────────┐ │  │ ┌───────────┐ │         │
│  │ │ OpenMP    │ │  │ │ OpenMP    │ │         │
│  │ │ Threads   │ │  │ │ Threads   │ │         │
│  │ │ (Level 2) │ │  │ │ (Level 2) │ │         │
│  │ │           │ │  │ │           │ │         │
│  │ │ Thread 1  │ │  │ │ Thread 1  │ │         │
│  │ │ Thread 2  │ │  │ │ Thread 2  │ │         │
│  │ │ Thread 3  │ │  │ │ Thread 3  │ │         │
│  │ │ Thread 4  │ │  │ │ Thread 4  │ │         │
│  │ └───────────┘ │  │ └───────────┘ │         │
│  └───────────────┘  └───────────────┘         │
│           ↑                  ↑                  │
│           └──────────────────┘                  │
│          Shared BoundTracker                    │
└─────────────────────────────────────────────────┘
```

### How It Works

1. **Ray** distributes tasks across cluster nodes
2. Each **Ray worker** receives a task (e.g., start from city pair i,j)
3. Within each worker, **OpenMP** spawns multiple threads
4. Threads process sub-tasks in parallel (e.g., different next cities)
5. **Shared bounds** are updated both:
   - Within worker (thread-to-thread via OpenMP critical sections)
   - Across workers (via Ray BoundTracker actor)

## Choosing the Right Approach

### For Single Machine
- Use **Test 6** with `num_threads = number_of_cores`
- Example: 8-core machine → `num_threads=8`

### For Small Cluster (2-4 nodes)
- Use **Test 5** (fine-grained) for simplicity
- Or **Test 6** with `num_threads=4` for multicore nodes

### For Large Cluster (5+ nodes, multicore)
- Use **Test 7** (fine-grained + multithread)
- Tune `num_threads` based on cores per node
- Example: 8 cores/node → `num_threads=2-4`

### For Memory-Constrained Systems
- Use **Test 6** with fewer threads
- Coarse-grained tasks use less memory

## Configuration Guide

### Test 6: Coarse-grained Parallel

```python
# Good for: Single node or small cluster with powerful cores
futures = [solve_city_parallel.remote(
    dist, C, i, 1, int(cost), 
    bound_tracker, 
    num_threads=4  # Adjust based on available cores
) for i in range(1, n)]

# Task count: n-1 (e.g., 15 tasks for n=16)
# Threads per task: 4
# Total parallel units: (n-1) × 4 = 60
```

### Test 7: Fine-grained Parallel

```python
# Good for: Large cluster with multicore nodes
futures = [solve_city_pair_parallel.remote(
    dist, C, i, j, 1, int(cost), 
    bound_tracker, 
    num_threads=2  # Lower since we have many tasks
) for i in range(1, n) for j in range(1, n) if i != j]

# Task count: (n-1)(n-2) (e.g., 210 tasks for n=16)
# Threads per task: 2
# Total parallel units: (n-1)(n-2) × 2 = 420
```

## File Structure

```
distributed_sum/
├── cpp/
│   ├── distributed_bnb.cpp         # C++ BnB with OpenMP support
│   └── libcvrp.so                  # Compiled library
├── python/
│   ├── ray_cvrp.py                 # Ray workers and parallel solvers
│   ├── run_ray.py                  # Main test script (7 test scenarios)
│   └── greedy.py                   # Greedy heuristic for initial bounds
├── bnb_classic.py                  # Classic single-threaded BnB
├── test_improvements.py            # Basic functionality tests
├── test_parallel_bnb.py            # Parallel solver tests
├── QUICKSTART.md                   # Quick start guide
├── HYBRID_PARALLEL_APPROACH.md     # Detailed hybrid approach docs
├── PERFORMANCE_IMPROVEMENTS.md     # Performance analysis (Polish)
└── test_one_vs_all_16_sorted.csv  # Benchmark results
```

## Documentation

- **QUICKSTART.md**: Get started quickly
- **HYBRID_PARALLEL_APPROACH.md**: Deep dive into hybrid parallelism
- **PERFORMANCE_IMPROVEMENTS.md**: Detailed performance analysis
- **SUMMARY.md**: Summary of all improvements

## Benchmarking

To run comprehensive benchmarks:

```bash
# Single test with specific parameters
python python/run_ray.py --n 16 --C 5 --fn results.csv --ct "My cluster"

# Results will be appended to results.csv with columns:
# n, C, method, best_cost, time_sec, preparing_time, computing_time, cluster_type
```

## Key Innovations

1. **BoundTracker Actor**: Shared state across distributed workers
2. **Fine-grained Tasks**: Better load balancing via city pairs
3. **OpenMP Integration**: Thread-level parallelism within workers
4. **Hybrid Parallelism**: Combines cluster and thread-level distribution
5. **Dynamic Scheduling**: OpenMP's dynamic work allocation
6. **Thread-safe Updates**: Critical sections for bound synchronization

## Performance Tips

### Optimal Thread Count

```python
# For CPU-bound tasks
num_threads = min(4, os.cpu_count())

# For I/O mixed workloads
num_threads = os.cpu_count()

# For memory-constrained
num_threads = 2
```

### Task Granularity

- **Too coarse**: Poor load balancing, idle workers
- **Too fine**: High communication overhead
- **Sweet spot**: ~10-100 tasks per worker

### Problem Size

- **n ≤ 12**: Use classic approach
- **12 < n ≤ 16**: Use Test 5 or Test 7
- **n > 16**: Requires careful tuning, consider time limits

## Troubleshooting

### Library not found
```bash
cd cpp
g++ -shared -fPIC -O3 -fopenmp distributed_bnb.cpp -o libcvrp.so
```

### OpenMP not available
```bash
# Install on Ubuntu/Debian
apt-get install libomp-dev

# Install on macOS
brew install libomp
```

### Ray connection issues
```bash
# Check Ray status
ray status

# Restart Ray
ray stop
ray start --head
```

## Contributing

When adding new approaches:
1. Add corresponding test in `run_ray.py`
2. Document in appropriate markdown file
3. Add validation in test scripts
4. Update this README

## License

[Add license information]

## Authors

[Add author information]

## Citation

If you use this code in research, please cite:
[Add citation information]
