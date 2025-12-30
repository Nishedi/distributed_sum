# Quick Reference: Using the Hybrid BnB Algorithm

## TL;DR

New hybrid multithread+cluster approach added! Use Test 6 or Test 7 for best performance.

```bash
# Compile (one-time)
cd cpp && g++ -shared -fPIC -O3 -fopenmp distributed_bnb.cpp -o libcvrp.so

# Run all tests (includes new Test 6 & 7)
python python/run_ray.py --n 16 --C 5

# Run with custom thread counts
python python/run_ray.py --n 16 --C 5 --threads-coarse 8 --threads-fine 4
```

## What's New?

Two new test scenarios that combine cluster and thread-level parallelism:

- **Test 6**: Hybrid coarse-grained (default: 4 threads per task)
- **Test 7**: Hybrid fine-grained (default: 2 threads per task)

## Which Test Should I Use?

| Your Setup | Recommended Test | Settings |
|------------|------------------|----------|
| Single machine (8 cores) | Test 6 | `--threads-coarse 8` |
| Small cluster (2-4 nodes) | Test 6 | `--threads-coarse 4` |
| Large cluster (5+ nodes) | Test 7 | `--threads-fine 2-4` |
| Memory-constrained | Test 6 | `--threads-coarse 2` |

## Expected Performance

Based on n=16, C=5:

- Test 1 (baseline): 246s
- Test 5 (previous best): 99s  
- **Test 6 (new)**: ~50-65s ⭐
- **Test 7 (new)**: ~40-50s ⭐⭐

## Command Examples

### Default Settings
```bash
python python/run_ray.py --n 16 --C 5
# Uses: Test 6 with 4 threads, Test 7 with 2 threads
```

### 8-Core Nodes
```bash
python python/run_ray.py --n 16 --C 5 --threads-coarse 8 --threads-fine 4
```

### 4-Core Nodes
```bash
python python/run_ray.py --n 14 --C 5 --threads-coarse 4 --threads-fine 2
```

### Memory-Constrained
```bash
python python/run_ray.py --n 14 --C 5 --threads-coarse 2 --threads-fine 1
```

## Testing Without Cluster

```bash
# Test basic functionality
python test_improvements.py

# Test parallel solver
python test_parallel_bnb.py

# See demo
python demo_hybrid_approach.py
```

## All Test Scenarios

1. **Test 1**: Basic BnB (baseline)
2. **Test 2**: BnB_SP (with greedy bound)
3. **Test 3**: BnB with shared bounds
4. **Test 4**: BnB_SP with shared bounds
5. **Test 5**: Fine-grained tasks (city pairs)
6. **Test 6**: Hybrid coarse-grained (multithread+cluster) ⭐
7. **Test 7**: Hybrid fine-grained (multithread+cluster) ⭐⭐

## Troubleshooting

### Compilation Error
```bash
# Make sure OpenMP is installed
# Ubuntu/Debian:
apt-get install libomp-dev

# macOS:
brew install libomp

# Then recompile:
cd cpp && g++ -shared -fPIC -O3 -fopenmp distributed_bnb.cpp -o libcvrp.so
```

### Library Not Found
```bash
# Check library exists
ls cpp/libcvrp.so

# If not, compile it
cd cpp && g++ -shared -fPIC -O3 -fopenmp distributed_bnb.cpp -o libcvrp.so
```

### Ray Connection Issues
```bash
# Check Ray status
ray status

# If needed, restart Ray
ray stop
ray start --head
```

## More Information

- **Quick Overview**: `QUICKSTART.md`
- **Technical Details**: `HYBRID_PARALLEL_APPROACH.md`
- **Complete Guide**: `README_COMPLETE.md`
- **Implementation Summary**: `IMPLEMENTATION_SUMMARY.md`

## Results

Results are saved to `results.csv` with columns:
- n, C, method, best_cost, time_sec, preparing_time, computing_time, cluster_type

Compare Test 6 and Test 7 against Test 5 to see improvement!
