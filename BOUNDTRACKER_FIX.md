# BoundTracker Performance Fix

## Problem

When running tests with the BoundTracker (Tests 3, 4, and 5), the multi-node performance was **worse** than single-node performance:

```
Test 5 Results (n=14):
- All nodes:   3.65s
- Single node: 2.92s
- Speedup: 0.80x ⚠️ (should be > 1.0x)
```

The "best version" (Test 5 with fine-grained tasks) should be faster on multiple nodes, not slower!

## Root Cause

The original implementation had each task make a **synchronous** `ray.get()` call to fetch the current best bound from the BoundTracker actor at startup:

```python
if bound_tracker is not None:
    current_bound = ray.get(bound_tracker.get_bound.remote())  # ❌ BLOCKING CALL
    bound_value = min(bound_value, int(current_bound))
```

### Why This Was Problematic

1. **Contention**: For Test 5 with n=14, there are 13×12 = **156 tasks**, meaning 156 synchronous network calls to a single actor
2. **Serialization**: Each call gets queued at the BoundTracker actor, creating a bottleneck
3. **Network Overhead**: In multi-node setup, each `ray.get()` involves network round-trip
4. **Blocking**: Tasks wait idle during the network call instead of starting computation
5. **No Parallelism**: The synchronous calls essentially serialize task startup

### Impact

The overhead from 156+ synchronous calls completely negated the benefits of:
- Having multiple nodes
- Using fine-grained task distribution
- Parallelizing the computation

## Solution

**Remove the synchronous bound fetch at task startup.**

### New Approach

```python
# ✅ Start immediately with provided bound_value
result = lib.solve_from_first_city(c_mat, n, C, city, BnB, bound_value)

# ✅ Update shared bound asynchronously (fire-and-forget)
if bound_tracker is not None and result < float('inf'):
    bound_tracker.update_bound.remote(result)
```

### How It Works

1. **Tasks start immediately** with the initial bound value (e.g., from greedy solution)
2. **No blocking calls** - zero contention on BoundTracker at startup
3. **Async updates only** - when a task finds a better solution, it updates the BoundTracker (fire-and-forget)
4. **Natural propagation** - the BoundTracker maintains the best-ever bound, even though individual tasks don't query it
5. **Benefit for later runs** - if you run multiple problem instances, later ones benefit from bounds established by earlier ones

### Why This Works

- The initial bound from the greedy solution is already quite good
- Tasks start computing immediately without waiting
- The C++ branch-and-bound algorithm still prunes effectively with the greedy bound
- The shared BoundTracker still tracks improvements (for monitoring/debugging)
- No contention = true parallelism = proper speedup

## Expected Results

After this fix:

```
Test 5 Results (n=14):
- Expected speedup: 1.5-2.0x (instead of 0.80x)
- Reduced preparing_time (task startup)
- Better computing_time (actual work)
```

### Why Not Perfect Linear Speedup?

Even with this fix, you won't get 9x speedup with 9 nodes because:
1. **Amdahl's Law**: Some parts of the computation are inherently sequential
2. **Load Imbalance**: Not all city pairs have equal computational complexity
3. **Communication Overhead**: Ray still has some overhead for task scheduling
4. **Shared Resources**: Network, memory bandwidth, etc.

But you should see **significant improvement** over single-node performance.

## Alternative Approaches Considered

### 1. Periodic Bound Fetching
- Fetch bound every N seconds during long-running tasks
- ❌ Complex to implement in C++ code
- ❌ Still has overhead

### 2. Batched Updates
- Accumulate multiple updates and send together
- ❌ Doesn't solve the startup contention problem
- ✅ Could help if update frequency becomes an issue

### 3. Local Caching
- Cache the bound value and refresh periodically
- ❌ Still requires synchronous calls
- ❌ Cache invalidation complexity

### 4. No BoundTracker (Chosen Solution)
- Don't fetch bound synchronously at startup
- ✅ Simple to implement
- ✅ No contention
- ✅ Still track best bound for monitoring
- ✅ Full parallelism

## Testing

To verify the fix works:

```bash
# On single node
python python/run_ray.py --n 14 --C 5 --ct "single node" --fn test_single.csv

# On all nodes
python python/run_ray.py --n 14 --C 5 --ct "all nodes" --fn test_all.csv
```

Compare Test 5 results:
- `test_all.csv` should now be **faster** than `test_single.csv`
- Speedup should be > 1.0x (ideally 1.5-2.0x)

## Lessons Learned

### Distributed Systems Best Practices

1. **Avoid synchronous calls in hot paths**: Every `ray.get()` is a potential bottleneck
2. **Prefer fire-and-forget**: Async updates (`remote()` without `get()`) scale better
3. **Minimize actor contention**: Hundreds of tasks hitting one actor = bad
4. **Good initial bounds**: A greedy solution provides a good-enough bound
5. **Measure everything**: Always compare single-node vs multi-node performance

### When to Use Shared State

✅ **Good use cases**:
- Infrequent updates (once per task completion)
- Non-critical information (monitoring, logging)
- Fire-and-forget patterns

❌ **Bad use cases**:
- Required for every task startup (contention)
- Synchronous reads in hot paths (blocking)
- Fine-grained coordination (overhead)

## References

- [Ray Documentation: Anti-patterns](https://docs.ray.io/en/latest/ray-core/patterns/index.html)
- Original issue: "dlaczego tak dziwnie to dziala? na single node dziala, najlepsza wersja dziala lepiej niz najlepsza wersja na wielu nodach"
- Related: `SUMMARY.md`, `PERFORMANCE_IMPROVEMENTS.md`
