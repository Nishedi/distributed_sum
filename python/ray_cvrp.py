# python/ray_cvrp.py

import ray
import ctypes
import numpy as np
import os


LIB_PATH = "/home/cluster/distributed_sum/cpp/libcvrp.so"
#LIB_PATH = "/home/kpempera/distributed_sum/cpp/libcvrp.so"


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


@ray.remote
def solve_city(dist_np, C, city, BnB, bound_value, bound_tracker=None, sync_interval=10000, time_interval=1.0):
    lib = ctypes.CDLL(LIB_PATH)

    n = dist_np.shape[0]

    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    if bound_tracker is not None:
        current_bound = ray.get(bound_tracker.get_bound.remote())
        bound_value = min(bound_value, int(current_bound))

    # Create callback function if bound_tracker is provided
    if bound_tracker is not None:
        # Define the callback function type for C++ (must be defined locally for Ray serialization)
        BOUND_QUERY_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p)
        
        # Use the _with_callback version
        lib.solve_from_first_city_with_callback.argtypes = [
            ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            BOUND_QUERY_CALLBACK,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_double
        ]
        lib.solve_from_first_city_with_callback.restype = ctypes.c_double

        # Create a callback that queries the bound tracker
        def query_bound_callback(user_data):
            try:
                current = ray.get(bound_tracker.get_bound.remote())
                return float(current)
            except Exception:  # Catch all exceptions to avoid crashing C++ code
                return float('inf')
        
        callback = BOUND_QUERY_CALLBACK(query_bound_callback)

        result = lib.solve_from_first_city_with_callback(
            c_mat, n, C, city, BnB, bound_value,
            callback,
            None,  # user_data
            sync_interval,
            time_interval
        )
    else:
        # Use the original version without callback
        lib.solve_from_first_city.argtypes = [
            ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int
        ]
        lib.solve_from_first_city.restype = ctypes.c_double
        
        result = lib.solve_from_first_city(c_mat, n, C, city, BnB, bound_value)
    
    if bound_tracker is not None and result < float('inf'):
        bound_tracker.update_bound.remote(result)
    
    return result


@ray.remote
def solve_city_pair(dist_np, C, city1, city2, BnB, bound_value, bound_tracker=None, sync_interval=10000, time_interval=1.0):
    lib = ctypes.CDLL(LIB_PATH)

    n = dist_np.shape[0]

    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    if bound_tracker is not None:
        current_bound = ray.get(bound_tracker.get_bound.remote())
        bound_value = min(bound_value, int(current_bound))

    # Create callback function if bound_tracker is provided
    if bound_tracker is not None:
        # Define the callback function type for C++ (must be defined locally for Ray serialization)
        BOUND_QUERY_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p)
        
        # Use the _with_callback version
        lib.solve_from_two_cities_with_callback.argtypes = [
            ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            BOUND_QUERY_CALLBACK,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_double
        ]
        lib.solve_from_two_cities_with_callback.restype = ctypes.c_double

        # Create a callback that queries the bound tracker
        def query_bound_callback(user_data):
            try:
                current = ray.get(bound_tracker.get_bound.remote())
                return float(current)
            except Exception:  # Catch all exceptions to avoid crashing C++ code
                return float('inf')
        
        callback = BOUND_QUERY_CALLBACK(query_bound_callback)

        result = lib.solve_from_two_cities_with_callback(
            c_mat, n, C, city1, city2, BnB, bound_value,
            callback,
            None,  # user_data
            sync_interval,
            time_interval
        )
    else:
        # Use the original version without callback
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
