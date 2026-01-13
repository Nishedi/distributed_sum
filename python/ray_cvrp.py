# python/ray_cvrp.py

import ray
import ctypes
import numpy as np
import os


LIB_PATH = "/home/cluster/distributed_sum/cpp/libcvrp.so"
#LIB_PATH = "/home/kpempera/distributed_sum/cpp/libcvrp.so"

# Define callback function types for C++
GET_BOUND_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p)
UPDATE_BOUND_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_double)


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


@ray.remote
def solve_city_with_sync(dist_np, C, city, BnB, bound_value, bound_tracker, 
                         sync_check_interval=1000, sync_time_interval_ms=100.0):
    """
    Solve CVRP starting from a specific city with synchronous bound updates.
    C++ will periodically query and update the bound via callbacks during computation.
    """
    lib = ctypes.CDLL(LIB_PATH)

    lib.solve_from_first_city_with_sync.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        GET_BOUND_CALLBACK,
        UPDATE_BOUND_CALLBACK,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_double
    ]
    lib.solve_from_first_city_with_sync.restype = ctypes.c_double

    n = dist_np.shape[0]

    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    # Create callback functions that interact with the bound_tracker
    @GET_BOUND_CALLBACK
    def get_bound_cb(context):
        """Callback for C++ to query current bound from host"""
        current = ray.get(bound_tracker.get_bound.remote())
        return float(current)
    
    @UPDATE_BOUND_CALLBACK
    def update_bound_cb(context, new_bound):
        """Callback for C++ to update bound on host"""
        # Fire-and-forget: We don't wait for the update to complete
        # This is intentional to avoid blocking C++ execution
        bound_tracker.update_bound.remote(new_bound)
    
    # Call the C++ function with callbacks
    result = lib.solve_from_first_city_with_sync(
        c_mat, n, C, city, BnB, bound_value,
        get_bound_cb, update_bound_cb, None,
        sync_check_interval, sync_time_interval_ms
    )
    
    return result


@ray.remote
def solve_city_pair_with_sync(dist_np, C, city1, city2, BnB, bound_value, bound_tracker,
                               sync_check_interval=1000, sync_time_interval_ms=100.0):
    """
    Solve CVRP starting from two specific cities with synchronous bound updates.
    C++ will periodically query and update the bound via callbacks during computation.
    """
    lib = ctypes.CDLL(LIB_PATH)

    lib.solve_from_two_cities_with_sync.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        GET_BOUND_CALLBACK,
        UPDATE_BOUND_CALLBACK,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_double
    ]
    lib.solve_from_two_cities_with_sync.restype = ctypes.c_double

    n = dist_np.shape[0]

    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    # Create callback functions that interact with the bound_tracker
    @GET_BOUND_CALLBACK
    def get_bound_cb(context):
        """Callback for C++ to query current bound from host"""
        current = ray.get(bound_tracker.get_bound.remote())
        return float(current)
    
    @UPDATE_BOUND_CALLBACK
    def update_bound_cb(context, new_bound):
        """Callback for C++ to update bound on host"""
        # Fire-and-forget: We don't wait for the update to complete
        # This is intentional to avoid blocking C++ execution
        bound_tracker.update_bound.remote(new_bound)
    
    # Call the C++ function with callbacks
    result = lib.solve_from_two_cities_with_sync(
        c_mat, n, C, city1, city2, BnB, bound_value,
        get_bound_cb, update_bound_cb, None,
        sync_check_interval, sync_time_interval_ms
    )
    
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
