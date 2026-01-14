# python/ray_cvrp.py

import ray
import ctypes
import numpy as np
import os


LIB_PATH = "/home/cluster/distributed_sum/cpp/libcvrp.so"
#LIB_PATH = "/home/kpempera/distributed_sum/cpp/libcvrp.so"

# lokalna kopia lowerbound i sprawdzac w remocie gdy jest znaleziony nowy
@ray.remote
class BoundTracker:
    def __init__(self, initial_bound):
        self.best_bound = initial_bound
    
    def update_bound(self, new_bound):
        if new_bound < self.best_bound:
            self.best_bound = new_bound
            return True
        return False
    
    def get_bound(self):
        return self.best_bound


CALLBACK_TYPE = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_double)


@ray.remote
def solve_city_active_sync(dist_np, C, city, BnB, bound_value, bound_tracker):
    """
    Solves CVRP starting from 'city', actively syncing bound with bound_tracker
    via a C++ callback.
    """
    lib = ctypes.CDLL(LIB_PATH)

    # Define argument types for the new C++ function
    lib.solve_with_callback.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        CALLBACK_TYPE  # The callback
    ]
    lib.solve_with_callback.restype = ctypes.c_double

    # Prepare Matrix
    n = dist_np.shape[0]
    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    # --- THE CALLBACK FUNCTION ---
    # This runs inside the worker process when C++ calls it.
    def py_callback(local_best_cost):
        # 1. Check if we should update global
        # Note: We use ray.get inside. This is synchronous.
        # Ideally, we verify local vs global cache to minimize Ray traffic,
        # but the C++ side already throttles calls (e.g. every 200ms).

        # Pull global best
        global_best = ray.get(bound_tracker.get_bound.remote())

        # If local is better, update global
        if local_best_cost < global_best:
            bound_tracker.update_bound.remote(local_best_cost)
            return float(local_best_cost)

        # Return the potentially tighter global bound to C++
        return float(global_best)

    # Create the C-callable function pointer
    c_callback = CALLBACK_TYPE(py_callback)

    # Initial check
    current_bound = ray.get(bound_tracker.get_bound.remote())
    bound_value = min(bound_value, int(current_bound))

    # Run Solver
    result = lib.solve_with_callback(c_mat, n, C, city, BnB, bound_value, c_callback)

    # Final update just in case
    if result < float('inf'):
        bound_tracker.update_bound.remote(result)

    return result
@ray.remote
def solve_city(dist_np, C, city, BnB, bound_value, bound_tracker=None):
    lib = ctypes.CDLL(LIB_PATH)

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

    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    if bound_tracker is not None:
        current_bound = ray.get(bound_tracker.get_bound.remote())
        bound_value = min(bound_value, int(current_bound))

    result = lib.solve_from_first_city(c_mat, n, C, city, BnB, bound_value)
    
    if bound_tracker is not None and result < float('inf'):
        bound_tracker.update_bound.remote(result)
    
    return result


@ray.remote
def solve_city_pair(dist_np, C, city1, city2, BnB, bound_value, bound_tracker=None):
    lib = ctypes.CDLL(LIB_PATH)

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

    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    if bound_tracker is not None:
        current_bound = ray.get(bound_tracker.get_bound.remote())
        bound_value = min(bound_value, int(current_bound))

    result = lib.solve_from_two_cities(c_mat, n, C, city1, city2, BnB, bound_value)
    
    if bound_tracker is not None and result < float('inf'):
        bound_tracker.update_bound.remote(result)
    
    return result


def run_distributed_bnb(n=12, C=5, BnB = 1, bound_value=1e18):
    coords = np.random.rand(n, 2) * 10000
    dist = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(coords[i] - coords[j])

    ray.init(address="auto")

    futures = [solve_city.remote(dist, C, i, BnB, bound_value) for i in range(1, n)]

    results = ray.get(futures)
    best_global = min(results)

    print(f"Best global cost: {best_global}")


if __name__ == "__main__":
    run_distributed_bnb()
