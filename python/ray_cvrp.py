# python/ray_cvrp.py

import ray
import ctypes
import numpy as np
import os


# Ścieżka absolutna do biblioteki C++
LIB_PATH = "/home/cluster/distributed_sum/cpp/libcvrp.so"
#LIB_PATH = "/home/kpempera/distributed_sum/cpp/libcvrp.so"


@ray.remote
class BoundTracker:
    """
    Shared actor to track the global best bound across all workers.
    This enables better pruning in the Branch and Bound algorithm.
    """
    def __init__(self, initial_bound):
        self.best_bound = initial_bound
    
    def update_bound(self, new_bound):
        """Update the best bound if the new bound is better."""
        if new_bound < self.best_bound:
            self.best_bound = new_bound
            return True
        return False
    
    def get_bound(self):
        """Get the current best bound."""
        return self.best_bound


@ray.remote
def solve_city(dist_np, C, city, BnB, bound_value, bound_tracker=None):
    """
    Funkcja wywoływana przez Ray worker.
    Konwertuje numpy array -> ctypes double** dopiero na workerze.
    """
    lib = ctypes.CDLL(LIB_PATH)

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

    # If we have a bound tracker, get the current best bound before starting
    if bound_tracker is not None:
        current_bound = ray.get(bound_tracker.get_bound.remote())
        bound_value = min(bound_value, int(current_bound))

    # Wywołanie C++ BnB dla pierwszego miasta
    result = lib.solve_from_first_city(c_mat, n, C, city, BnB, bound_value)
    
    # Update the global bound if we found a better solution
    if bound_tracker is not None and result < float('inf'):
        bound_tracker.update_bound.remote(result)
    
    return result


def run_distributed_bnb(n=12, C=5, BnB = 1, bound_value=1e18):
    # Tworzenie losowych danych
    coords = np.random.rand(n, 2) * 10000
    dist = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(coords[i] - coords[j])

    # Uruchomienie Ray cluster
    ray.init(address="auto")

    # Tworzymy zadania dla każdego pierwszego miasta (oprócz startowego 0)
    futures = [solve_city.remote(dist, C, i, BnB, bound_value) for i in range(1, n)]

    # Pobranie wyników
    results = ray.get(futures)
    best_global = min(results)

    print(f"Best global cost: {best_global}")


if __name__ == "__main__":
    run_distributed_bnb()
