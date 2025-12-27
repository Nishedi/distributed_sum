# Fault Tolerance in Distributed Sum

## Problem Statement (Polski)
**Dlaczego jak wyłącze jednego node to nie działa i się wykłada, jak są wszystkie to działa**

Translation: "Why does it not work and crash when I disable one node, but works when all nodes are active?"

## Solution Overview

This document describes the fault tolerance improvements made to the distributed computing system to handle node failures gracefully.

### Root Cause

The original implementation had the following issues:

1. **No retry mechanism**: Ray remote functions didn't retry on failures
2. **No error handling**: `ray.get(futures)` would crash if any task failed
3. **Single point of failure**: If one node died during execution, the entire computation would fail
4. **No graceful degradation**: The system couldn't continue with partial results

### Changes Made

#### 1. Added Automatic Retries to Ray Remote Functions

**Before:**
```python
@ray.remote
def solve_city(dist_np, C, city):
    # ... function code
```

**After:**
```python
@ray.remote(max_retries=3, retry_exceptions=True)
def solve_city(dist_np, C, city):
    # ... function code
```

This ensures that if a task fails (e.g., due to node failure), Ray will automatically retry it up to 3 times, potentially on a different node.

#### 2. Added Error Handling to Ray Initialization

**Before:**
```python
ray.init(address="auto")
```

**After:**
```python
ray.init(
    address="auto",
    ignore_reinit_error=True,
    _temp_dir="/tmp/ray"
)
```

Benefits:
- `ignore_reinit_error=True`: Prevents crashes when Ray is already initialized
- `_temp_dir="/tmp/ray"`: Uses a consistent temporary directory

#### 3. Implemented Graceful Error Handling for Task Results

**Before:**
```python
futures = [solve_city.remote(dist, C, i) for i in range(1, n)]
results = ray.get(futures)  # ❌ Crashes if any task fails
best_global = min(results)
```

**After:**
```python
futures = [solve_city.remote(dist, C, i) for i in range(1, n)]

# Pobranie wyników z obsługą błędów
results = []
for future in futures:
    try:
        result = ray.get(future)
        results.append(result)
    except Exception as e:
        print(f"Warning: Task failed with error: {e}. Skipping...")
        continue

if not results:
    print("Error: All tasks failed!")
    return None

best_global = min(results)
```

Benefits:
- System continues even if some tasks fail
- Provides informative warnings about failures
- Returns the best result from successful tasks
- Only fails if ALL tasks fail (not just one)

## Files Modified

1. **`python/ray_cvrp.py`**
   - Added retry mechanism to `solve_city` function
   - Improved `run_distributed_bnb` with error handling
   - Returns None if all tasks fail

2. **`python/run_ray_copy.py`**
   - Added fault-tolerant Ray initialization
   - Individual error handling for each task
   - Reports completion statistics

3. **`python/run_ray.py`**
   - Updated `run_experiment` function with error handling
   - All three execution modes now fault-tolerant
   - Returns None for failed experiments

4. **`python/ray_sum.py`**
   - Consistent fault tolerance patterns
   - Handles partial results

## Expected Behavior

### Before Changes ❌
- System: 9 nodes active
- Action: Disable 1 node
- Result: **Entire computation crashes**
- Error: `Worker unexpectedly exits with a connection error`

### After Changes ✓
- System: 9 nodes active  
- Action: Disable 1 node
- Result: **Computation continues with 8 nodes**
- Output: 
  ```
  Warning: Task for city 5 failed with error: ... Skipping...
  Completed 10/11 tasks successfully
  Best global cost: 12345.67
  ```

## Testing Recommendations

To test the fault tolerance:

1. **Start the Ray cluster** with all nodes
   ```bash
   ray start --head --port=6379
   # On other nodes:
   ray start --address=<HEAD_IP>:6379
   ```

2. **Run the computation**
   ```bash
   python python/run_ray_copy.py
   ```

3. **During execution, stop one node**
   ```bash
   # On one worker node:
   ray stop
   ```

4. **Expected outcome**: 
   - The computation continues
   - Some tasks may be retried
   - Final result is computed from successful tasks
   - System does NOT crash

## Additional Notes

- **Max retries**: Set to 3 for good balance between resilience and performance
- **Task distribution**: Ray will automatically redistribute failed tasks to healthy nodes
- **Performance impact**: Minimal overhead when all nodes are healthy
- **Partial results**: System can produce results even if minority of nodes fail

## Troubleshooting

If you still experience crashes:

1. Check that all nodes can reach each other over the network
2. Verify Ray versions are consistent across all nodes
3. Check logs for specific error messages: `ray logs`
4. Increase max_retries if nodes are frequently failing temporarily
5. Consider setting Ray's `max_task_retries` parameter in ray.init()

## Polish Translation / Tłumaczenie

**Problem:** System się wykłada gdy jeden węzeł przestaje działać.

**Rozwiązanie:** 
- Dodano automatyczne ponawianie prób (retry) dla zadań
- Dodano obsługę błędów dla każdego zadania indywidualnie
- System kontynuuje pracę z dostępnymi węzłami
- Zwraca najlepszy wynik z udanych zadań

**Oczekiwane zachowanie:**
- Gdy węzeł przestaje działać, jego zadania są ponawiane na innych węzłach
- Obliczenia trwają z mniejszą liczbą węzłów
- System nie crashuje, tylko pokazuje ostrzeżenia
- Wynik jest obliczany z pomyślnie wykonanych zadań
