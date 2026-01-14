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
    # 1. Load library inside the function
    lib = ctypes.CDLL(LIB_PATH)

    # 2. Define Callback Type INSIDE the function to avoid pickling errors
    CALLBACK_TYPE = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_double)

    # 3. Setup argtypes
    lib.solve_with_callback.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),  # dist matrix
        ctypes.c_int,  # n
        ctypes.c_int,  # C
        ctypes.c_int,  # city
        ctypes.c_int,  # cutting
        ctypes.c_int,  # bound_value
        CALLBACK_TYPE  # callback function
    ]
    lib.solve_with_callback.restype = ctypes.c_double

    # 4. Prepare Data
    n = dist_np.shape[0]
    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    # 5. Define the Python Callback
    def py_callback(local_best_cost):
        # Synchronous check with Ray actor (blocking this worker briefly)
        # Note: We use ray.get here. C++ calls this function.
        try:
            global_best = ray.get(bound_tracker.get_bound.remote())

            if local_best_cost < global_best:
                bound_tracker.update_bound.remote(local_best_cost)
                return float(local_best_cost)

            return float(global_best)
        except Exception as e:
            # Fallback in case of ray communication error
            return float(local_best_cost)

    # 6. Create C-callable pointer
    c_callback = CALLBACK_TYPE(py_callback)

    # 7. Initial Bound Check
    current_bound = ray.get(bound_tracker.get_bound.remote())
    bound_value = min(bound_value, int(current_bound))

    # 8. Run Solver
    result = lib.solve_with_callback(c_mat, n, C, city, BnB, bound_value, c_callback)

    # Final update
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
