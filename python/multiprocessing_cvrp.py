# python/multiprocessing_cvrp.py

import ctypes
import numpy as np
import multiprocessing as mp
from multiprocessing import Manager, Pool, cpu_count


# Ścieżka absolutna do biblioteki C++
# Try multiple paths for compatibility with different environments
import os

# Check environment variable first
if 'CVRP_LIB_PATH' in os.environ:
    LIB_PATH = os.environ['CVRP_LIB_PATH']
else:
    LIB_PATH_OPTIONS = [
        "/home/cluster/distributed_sum/cpp/libcvrp.so",
        "/home/runner/work/distributed_sum/distributed_sum/cpp/libcvrp.so",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cpp", "libcvrp.so")
    ]

    # Find the first path that exists
    LIB_PATH = None
    for path in LIB_PATH_OPTIONS:
        if os.path.exists(path):
            LIB_PATH = path
            break

    if LIB_PATH is None:
        # Default to the relative path if none exist
        LIB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cpp", "libcvrp.so")


def init_worker(shared_bound, lock):
    """Initialize worker process with shared state"""
    global worker_shared_bound
    global worker_lock
    worker_shared_bound = shared_bound
    worker_lock = lock


def solve_city_mp(args):
    """
    Multiprocessing worker function for solving from a single city.
    Uses shared memory for bound tracking.
    """
    dist_np, C, city, BnB, initial_bound = args
    
    try:
        lib = ctypes.CDLL(LIB_PATH)
    except OSError as e:
        print(f"Error loading library from {LIB_PATH}: {e}")
        print(f"Please ensure the C++ library is compiled and the path is correct.")
        return float('inf')

    # Deklaracja sygnatury C++
    lib.solve_from_first_city.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int
    ]
    lib.solve_from_first_city.restype = ctypes.c_double

    n = dist_np.shape[0]

    # Konwersja numpy -> double**
    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    # Get current best bound from shared state
    with worker_lock:
        bound_value = int(min(initial_bound, worker_shared_bound.value))

    # Wywołanie C++ BnB dla pierwszego miasta
    result = lib.solve_from_first_city(c_mat, n, C, city, BnB, bound_value)
    
    # Update the global bound if we found a better solution
    if result < float('inf'):
        with worker_lock:
            if result < worker_shared_bound.value:
                worker_shared_bound.value = result
    
    return result


def solve_city_pair_mp(args):
    """
    Multiprocessing worker function for solving from a city pair.
    Provides finer-grained task distribution.
    """
    dist_np, C, city1, city2, BnB, initial_bound = args
    
    try:
        lib = ctypes.CDLL(LIB_PATH)
    except OSError as e:
        print(f"Error loading library from {LIB_PATH}: {e}")
        print(f"Please ensure the C++ library is compiled and the path is correct.")
        return float('inf')

    # Deklaracja sygnatury dla funkcji rozwiązującej z dwoma pierwszymi miastami
    lib.solve_from_two_cities.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int
    ]
    lib.solve_from_two_cities.restype = ctypes.c_double

    n = dist_np.shape[0]

    # Konwersja numpy -> double**
    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    # Get current best bound from shared state
    with worker_lock:
        bound_value = int(min(initial_bound, worker_shared_bound.value))

    # Wywołanie C++ BnB dla pierwszych dwóch miast
    result = lib.solve_from_two_cities(c_mat, n, C, city1, city2, BnB, bound_value)
    
    # Update the global bound if we found a better solution
    if result < float('inf'):
        with worker_lock:
            if result < worker_shared_bound.value:
                worker_shared_bound.value = result
    
    return result


def run_distributed_bnb_mp(n=12, C=5, BnB=1, bound_value=1e18, use_pairs=False, num_workers=None):
    """
    Run distributed Branch and Bound using Python multiprocessing.
    
    Args:
        n: Number of cities
        C: Vehicle capacity
        BnB: Branch and bound flag (1 for enabled, 0 for brute force)
        bound_value: Initial bound value
        use_pairs: If True, use city pairs for finer-grained tasks
        num_workers: Number of worker processes (defaults to CPU count)
    
    Returns:
        best_global: Best cost found
    """
    # Tworzenie losowych danych
    coords = np.random.rand(n, 2) * 10000
    dist = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(coords[i] - coords[j])

    # Setup multiprocessing
    if num_workers is None:
        num_workers = cpu_count()
    
    # Create shared state for bound tracking
    manager = Manager()
    shared_bound = manager.Value('d', bound_value)
    lock = manager.Lock()
    
    # Create task list
    if use_pairs:
        # Fine-grained tasks with city pairs
        tasks = [(dist, C, i, j, BnB, bound_value) 
                 for i in range(1, n) for j in range(1, n) if i != j]
        worker_func = solve_city_pair_mp
    else:
        # Coarse-grained tasks with single cities
        tasks = [(dist, C, i, BnB, bound_value) for i in range(1, n)]
        worker_func = solve_city_mp
    
    # Run tasks in parallel
    with Pool(processes=num_workers, initializer=init_worker, 
              initargs=(shared_bound, lock)) as pool:
        results = pool.map(worker_func, tasks)
    
    # Filter out infinity results and check if we got valid results
    valid_results = [r for r in results if r < float('inf')]
    
    if not valid_results:
        raise RuntimeError(
            "No valid results obtained from workers. "
            "This likely means the C++ library failed to load. "
            f"Check that {LIB_PATH} exists and is accessible."
        )
    
    best_global = min(valid_results)
    
    return best_global


if __name__ == "__main__":
    print("=== Multiprocessing-based Distributed CVRP ===")
    print(f"Available CPU cores: {cpu_count()}")
    print()
    
    # Test with 12 cities
    n = 12
    C = 5
    
    print(f"Testing with n={n}, C={C}")
    print()
    
    # Test 1: Coarse-grained (single cities)
    print("Test 1: Coarse-grained tasks (single cities)")
    result = run_distributed_bnb_mp(n=n, C=C, BnB=1, bound_value=999999999, use_pairs=False)
    print(f"Best cost: {result}")
    print()
    
    # Test 2: Fine-grained (city pairs)
    print("Test 2: Fine-grained tasks (city pairs)")
    result = run_distributed_bnb_mp(n=n, C=C, BnB=1, bound_value=999999999, use_pairs=True)
    print(f"Best cost: {result}")
