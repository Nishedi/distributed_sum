# Upper Bound Synchronization Feature

## Overview

This document describes the new upper bound synchronization feature that allows C++ solvers to periodically synchronize their upper bound with the Python host during execution.

## Problem Statement

Previously, C++ workers would:
1. Get the initial upper bound from the host at the start
2. Run completely independently without any synchronization
3. Update the host bound only after completion

This meant that if one worker found a better solution, other workers couldn't benefit from this improved bound until they finished, leading to wasted computation.

## Solution

The new implementation adds a **callback mechanism** that allows C++ to:
1. Periodically pause execution (without stopping)
2. Query the host for the current best upper bound
3. Update its local bound if the host has a better one
4. Continue execution with the improved bound

### Key Features

1. **Non-blocking**: C++ pauses briefly but doesn't stop during synchronization
2. **Throttled**: Updates are controlled by both iteration count and time to avoid excessive overhead
3. **Backward compatible**: Original API remains unchanged
4. **Configurable**: Synchronization frequency can be adjusted per use case

## Implementation Details

### C++ Changes

#### New Data Structures

```cpp
typedef double (*BoundQueryCallback)(void* user_data);
```

The callback type that Python can implement to provide bound queries.

#### CVRP_BnB Class Extensions

```cpp
class CVRP_BnB {
    // ... existing fields ...
    
    // Synchronization parameters
    BoundQueryCallback bound_callback;
    void* callback_user_data;
    int sync_check_interval;        // Minimum iterations between sync
    double sync_time_interval;      // Minimum seconds between sync
    int iterations_since_sync;
    chrono::steady_clock::time_point last_sync_time;
    int sync_count;
}
```

#### Synchronization Logic

```cpp
void check_and_sync_bound() {
    if (bound_callback == nullptr) return;
    
    iterations_since_sync++;
    
    // Check if enough iterations have passed
    if (iterations_since_sync < sync_check_interval) return;
    
    // Check if enough time has passed
    auto now = chrono::steady_clock::now();
    chrono::duration<double> elapsed = now - last_sync_time;
    if (elapsed.count() < sync_time_interval) return;
    
    // Perform synchronization
    double host_bound = bound_callback(callback_user_data);
    if (host_bound < best_cost) {
        best_cost = host_bound;
    }
    
    // Reset counters
    iterations_since_sync = 0;
    last_sync_time = now;
    sync_count++;
}
```

This is called in the `branch_and_bound` method after each bound check.

#### New C API Functions

Two new functions with callback support:

```cpp
double solve_from_first_city_with_callback(
    double** dist, int n, int C, int first_city, 
    int cutting, int bound_value,
    BoundQueryCallback callback, void* user_data,
    int sync_interval, double time_interval
);

double solve_from_two_cities_with_callback(
    double** dist, int n, int C, int first_city, int second_city,
    int cutting, int bound_value,
    BoundQueryCallback callback, void* user_data,
    int sync_interval, double time_interval
);
```

Original functions remain unchanged for backward compatibility:
```cpp
double solve_from_first_city(double** dist, int n, int C, int first_city, int cutting, int bound_value);
double solve_from_two_cities(double** dist, int n, int C, int first_city, int second_city, int cutting, int bound_value);
```

### Python Changes

#### Callback Type Definition

```python
BOUND_QUERY_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p)
```

#### Updated Ray Functions

The `solve_city` and `solve_city_pair` functions now:
1. Accept optional `sync_interval` and `time_interval` parameters
2. Create a callback function if `bound_tracker` is provided
3. Use `_with_callback` C++ functions when callback is needed
4. Fall back to original functions when no callback is needed

Example from `solve_city`:
```python
@ray.remote
def solve_city(dist_np, C, city, BnB, bound_value, bound_tracker=None, 
               sync_interval=10000, time_interval=1.0):
    # ... setup code ...
    
    if bound_tracker is not None:
        # Create callback
        def query_bound_callback(user_data):
            try:
                current = ray.get(bound_tracker.get_bound.remote())
                return float(current)
            except:
                return float('inf')
        
        callback = BOUND_QUERY_CALLBACK(query_bound_callback)
        
        # Use callback version
        result = lib.solve_from_first_city_with_callback(
            c_mat, n, C, city, BnB, bound_value,
            callback, None, sync_interval, time_interval
        )
    else:
        # Use original version
        result = lib.solve_from_first_city(c_mat, n, C, city, BnB, bound_value)
    
    # ... rest of code ...
```

## Usage

### Basic Usage (Existing Tests)

The existing tests in `run_ray.py` will automatically benefit from this feature without any changes, as the default behavior is maintained.

### Custom Synchronization Parameters

To customize synchronization frequency:

```python
# More frequent synchronization (every 5000 iterations or 0.5 seconds)
futures = [solve_city.remote(
    dist, C, i, 1, int(cost), bound_tracker, 
    sync_interval=5000, 
    time_interval=0.5
) for i in range(1, n)]

# Less frequent synchronization (every 20000 iterations or 2 seconds)
futures = [solve_city.remote(
    dist, C, i, 1, int(cost), bound_tracker,
    sync_interval=20000,
    time_interval=2.0
) for i in range(1, n)]
```

### Backward Compatibility

Code without `bound_tracker` continues to work unchanged:

```python
# This still works exactly as before
futures = [solve_city.remote(dist, C, i, 1, 999999999) for i in range(1, n)]
```

## Configuration Parameters

### `sync_interval` (default: 10000)
- Minimum number of iterations between synchronization checks
- Higher values = less frequent sync, lower overhead
- Lower values = more frequent sync, better bound propagation

### `time_interval` (default: 1.0)
- Minimum seconds between synchronization checks
- Ensures synchronization happens even if iteration count is slow
- Prevents synchronization if iteration count is reached too quickly

### Choosing Parameters

**For large problems (n > 15):**
- Use higher intervals: `sync_interval=10000, time_interval=1.0` (default)
- Reduces overhead while still providing benefit

**For medium problems (n = 10-15):**
- Use moderate intervals: `sync_interval=5000, time_interval=0.5`
- Balances overhead and benefit

**For small problems (n < 10):**
- Synchronization may not be beneficial due to overhead
- Consider disabling by not passing `bound_tracker`

## Performance Considerations

1. **Overhead**: Each synchronization involves:
   - A Ray remote call to query the bound
   - Network communication in distributed setups
   - Minimal CPU time for comparison

2. **Benefits**: 
   - Better pruning in Branch and Bound
   - Reduced total computation time
   - More efficient resource utilization

3. **Trade-off**: 
   - More frequent sync = higher overhead but better pruning
   - Less frequent sync = lower overhead but potentially more wasted work

## Testing

Three test files are provided:

1. **`test_library.py`**: Basic library loading and API verification
2. **`test_callback_larger.py`**: Callback mechanism verification with timing
3. **`test_sync.py`**: Ray-based distributed testing (requires Ray cluster)

Run tests:
```bash
# Basic library test
python test_library.py

# Callback mechanism test
python test_callback_larger.py

# Full integration test (requires Ray)
python test_sync.py
```

## Migration Guide

### For Existing Code

No changes required! The implementation is backward compatible.

### To Enable Synchronization

Simply ensure `bound_tracker` is passed to `solve_city` or `solve_city_pair`:

```python
# Before (still works)
futures = [solve_city.remote(dist, C, i, 1, int(cost)) for i in range(1, n)]

# After (with synchronization)
bound_tracker = BoundTracker.remote(int(cost))
futures = [solve_city.remote(dist, C, i, 1, int(cost), bound_tracker) for i in range(1, n)]
```

### To Customize Synchronization

Add the optional parameters:

```python
futures = [solve_city.remote(
    dist, C, i, 1, int(cost), bound_tracker,
    sync_interval=5000,
    time_interval=0.5
) for i in range(1, n)]
```

## Technical Notes

1. **Thread Safety**: The callback mechanism uses Ray's built-in thread-safe remote calls
2. **Memory Management**: Callbacks are kept alive by ctypes during C++ execution
3. **Error Handling**: Callback exceptions return infinity to avoid crashes
4. **Compiler Support**: Requires C++11 or later for `chrono` support

## Future Improvements

Possible enhancements:
1. Adaptive synchronization frequency based on improvement rate
2. Batch synchronization for multiple workers
3. Async callback returns to eliminate blocking
4. Statistics collection (sync count, time saved, etc.)
