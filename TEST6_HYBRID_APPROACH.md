# Test 6: Hybrid Batched Approach - Distributed + Multithread Optimization

## Problem Analysis

From `test_one_vs_all_16_sorted.csv`, we observed an interesting pattern:

### Tests 1 & 2 (Original approaches):
- **Cluster multithread**: BEST performance (10.53x and 8.81x speedup)
- Successfully utilizes both distributed nodes AND multithread capabilities

### Tests 3, 4, 5 (Improved approaches with shared bounds):
- **Cluster single threads**: Better than cluster multithread
- Test 5 example: 99.6s (single thread) vs 138.5s (multithread)
- **Problem**: Too fine-grained tasks create overhead that negates multithread benefits

## Root Cause

When tasks are **too fine-grained** (Test 5: 210 tasks for n=16):
- Each task completes too quickly (~0.5s per task)
- Multithread overhead (context switching, synchronization) becomes significant
- Ray task scheduling overhead dominates
- No time for multithread to show benefits within each task

When tasks are **too coarse-grained** (Test 1: 15 tasks for n=16):
- Better multithread utilization within each task
- BUT poor load balancing (some tasks take much longer)
- Total time limited by slowest task

## Solution: Hybrid Batched Approach (Test 6)

### Key Innovation
**Balance task granularity for BOTH distributed AND multithread optimization**

### Design Principles
1. **Not too fine**: Each task should have enough work for multithread to be beneficial
2. **Not too coarse**: Enough tasks for good load balancing across nodes
3. **Adaptive**: Batch size scales with problem size

### Implementation

```python
# Group city pairs into batches
all_pairs = [(i, j) for i in range(1, n) for j in range(1, n) if i != j]
batch_size = max(4, len(all_pairs) // 40)  # Target ~40 batches

batches = []
for i in range(0, len(all_pairs), batch_size):
    batches.append(all_pairs[i:i+batch_size])

# Each batch is processed as one task
futures = [solve_city_pairs_batch.remote(dist, C, batch, 1, int(cost), bound_tracker) 
           for batch in batches]
```

### New Function: `solve_city_pairs_batch`

Processes multiple city pairs in a single Ray task:
- Gets bound once per batch (reduces communication overhead)
- Processes pairs sequentially within batch (benefits from multithread)
- Updates bound when better solutions found
- Each batch has enough work (~4-5 pairs) for meaningful computation

## Expected Results

### For n=16 (210 city pairs total):

| Approach | Task Count | Work per Task | Distributed | Multithread | Expected Time |
|----------|-----------|---------------|-------------|-------------|---------------|
| Test 5 (fine-grained) | 210 | 1 pair (~0.5s) | ✓ Excellent | ✗ No benefit | ~100s |
| Test 1 (coarse) | 15 | All pairs from city | ✓ Poor | ✓ Good | ~250s |
| **Test 6 (hybrid)** | **~40** | **4-5 pairs (~2-3s)** | **✓ Good** | **✓ Good** | **~70-80s** |

### Speedup Analysis

**Single Thread baseline**: ~600s
**Test 6 expected speedup**:
- From distributed (40 tasks on 9 nodes): ~3-4x
- From multithread per task (within node): ~2-3x  
- **Combined**: ~8-10x total speedup
- **Expected time**: 60-75s

## Why This Works

1. **Optimal task granularity**: 
   - 2-3 seconds per task allows multithread to show benefits
   - Reduces Ray scheduling overhead

2. **Good load balancing**:
   - ~40 tasks can be distributed efficiently across 9 nodes
   - No single bottleneck task

3. **Efficient bound sharing**:
   - One bound fetch per batch (not per pair)
   - Immediate updates when better solutions found

4. **Multithread benefits**:
   - Each task has enough work for CPU cores to be utilized
   - Branch and bound naturally benefits from parallel execution

## Usage

The test is integrated into `python/run_ray.py` as Test 6:

```bash
python python/run_ray.py --n 16 --C 5 --ct "Cluster multithread"
```

Results will be saved to the CSV file with method:
`"Test 6: Hybrydowe podejście z grupowaniem zadań (DISTRIBUTED + MULTITHREAD)"`

## Comparison Summary

| Test | Approach | Best For | Speedup (n=16) |
|------|----------|----------|----------------|
| 1 | Original BnB | Baseline | 10.53x (cluster MT) |
| 2 | BnB_SP | Baseline with greedy | 8.81x (cluster MT) |
| 3 | Shared bound | Improved pruning | 2.55x (cluster MT) |
| 4 | Shared bound + greedy | Improved pruning | 2.46x (cluster MT) |
| 5 | Fine-grained pairs | Best distributed | 4.34x (cluster ST) |
| **6** | **Hybrid batched** | **Best combined** | **~10-12x (cluster MT)** |

## Technical Details

### Batch Size Selection
```python
batch_size = max(4, len(all_pairs) // 40)
```

- **Minimum 4 pairs**: Ensures each task has meaningful work
- **~40 batches total**: Good distribution across typical cluster sizes (4-16 nodes)
- **Adaptive**: Automatically scales with problem size

### Within-Batch Processing
```python
best_result = float('inf')
for city1, city2 in city_pairs:
    result = lib.solve_from_two_cities(c_mat, n, C, city1, city2, BnB, bound_value)
    if result < best_result:
        best_result = result
        bound_tracker.update_bound.remote(best_result)
        bound_value = int(best_result)  # Use for remaining pairs in batch
```

Benefits:
- Sequential processing allows bound improvement within batch
- Later pairs in batch benefit from earlier discoveries
- Reduces redundant computation

## Conclusion

Test 6 demonstrates that the **best performance comes from balancing**:
- **Distributed execution**: Multiple nodes working in parallel
- **Multithread execution**: Multiple cores within each node
- **Task granularity**: Neither too fine nor too coarse

This hybrid approach should show **~10-12x speedup** with cluster multithread configuration, combining the benefits of both parallelization strategies.
