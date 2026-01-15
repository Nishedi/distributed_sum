# python/ray_cvrp.py

import ray
import ctypes
import numpy as np
import os
import time


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
def solve_city_active_sync(dist_np, C, city, BnB, bound_value, bound_tracker, sync_iters, sync_time):
    lib = ctypes.CDLL(LIB_PATH)

    CALLBACK_TYPE = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_double)

    # ZAKTUALIZOWANA LISTA ARGUMENTÓW
    # Kolejność musi zgadzać się z C++:
    # ..., int* out_syncs, BoundCallback cb, int sync_iters, int sync_time
    lib.solve_with_callback.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),  # dist
        ctypes.c_int,  # n
        ctypes.c_int,  # C
        ctypes.c_int,  # city
        ctypes.c_int,  # cutting
        ctypes.c_int,  # bound_value
        ctypes.POINTER(ctypes.c_int),  # out_syncs
        CALLBACK_TYPE,  # cb
        ctypes.c_int,  # NOWE: sync_iters
        ctypes.c_int  # NOWE: sync_time
    ]
    lib.solve_with_callback.restype = ctypes.c_double

    n = dist_np.shape[0]
    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        c_mat[i] = (ctypes.c_double * n)(*dist_np[i])

    def py_callback(local_best_cost):
        try:
            global_best = ray.get(bound_tracker.get_bound.remote())
            if local_best_cost < global_best:
                bound_tracker.update_bound.remote(local_best_cost)
                return float(local_best_cost)
            return float(global_best)
        except:
            return float(local_best_cost)

    c_callback = CALLBACK_TYPE(py_callback)
    c_sync_counter = ctypes.c_int(0)

    current_bound = ray.get(bound_tracker.get_bound.remote())
    bound_value = min(bound_value, int(current_bound))


    start_task = time.time()
    result = lib.solve_with_callback(
        c_mat, n, C, city, BnB, bound_value,
        ctypes.byref(c_sync_counter), c_callback,
        sync_iters, sync_time
    )
    duration = time.time() - start_task

    if result < float('inf'):
        bound_tracker.update_bound.remote(result)

    return result, c_sync_counter.value, duration
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


@ray.remote
def solve_city_pair_active_sync(dist_np, C, city1, city2, BnB, bound_value, bound_tracker, sync_iters, sync_time):
    lib = ctypes.CDLL(LIB_PATH)

    # Definicja typu callback (musi być wewnątrz funkcji)
    CALLBACK_TYPE = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_double)

    # Definicja argumentów dla NOWEJ funkcji C++
    lib.solve_pair_with_callback.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,  # n
        ctypes.c_int,  # C
        ctypes.c_int,  # city1
        ctypes.c_int,  # city2
        ctypes.c_int,  # cutting
        ctypes.c_int,  # bound_value
        ctypes.POINTER(ctypes.c_int),  # out_syncs
        CALLBACK_TYPE,  # callback
        ctypes.c_int,  # sync_iters
        ctypes.c_int  # sync_time
    ]
    lib.solve_pair_with_callback.restype = ctypes.c_double

    # Przygotowanie macierzy
    n = dist_np.shape[0]
    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        c_mat[i] = (ctypes.c_double * n)(*dist_np[i])

    # Callback (identyczny jak w Teście 6)
    def py_callback(local_best_cost):
        try:
            global_best = ray.get(bound_tracker.get_bound.remote())
            if local_best_cost < global_best:
                bound_tracker.update_bound.remote(local_best_cost)
                return float(local_best_cost)
            return float(global_best)
        except:
            return float(local_best_cost)

    c_callback = CALLBACK_TYPE(py_callback)
    c_sync_counter = ctypes.c_int(0)

    # Pobranie początkowego ograniczenia
    current_bound = ray.get(bound_tracker.get_bound.remote())
    bound_value = min(bound_value, int(current_bound))

    # POMIAR CZASU
    start_task = time.time()

    # WYWOŁANIE NOWEJ FUNKCJI C++
    result = lib.solve_pair_with_callback(
        c_mat, n, C, city1, city2, BnB, bound_value,
        ctypes.byref(c_sync_counter), c_callback,
        sync_iters, sync_time
    )

    duration = time.time() - start_task

    if result < float('inf'):
        bound_tracker.update_bound.remote(result)

    return result, c_sync_counter.value, duration


@ray.remote
def solve_whole_instance_node_parallel(dist_np, C, BnB, bound_value):
    """
    Rozwiązuje całą instancję CVRP na jednym workerze (bez komunikacji sieciowej).
    """
    lib = ctypes.CDLL(LIB_PATH)

    lib.solve_complete_problem.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,  # n
        ctypes.c_int,  # C
        ctypes.c_int,  # cutting
        ctypes.c_int  # bound_value
    ]
    lib.solve_complete_problem.restype = ctypes.c_double

    n = dist_np.shape[0]
    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        c_mat[i] = (ctypes.c_double * n)(*dist_np[i])

    result = lib.solve_complete_problem(c_mat, n, C, BnB, bound_value)

    return result


if __name__ == "__main__":
    run_distributed_bnb()
