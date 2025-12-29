# python/ray_cvrp.py

import ray
import ctypes
import numpy as np
import os


# Ścieżka absolutna do biblioteki C++
LIB_PATH = "/home/cluster/distributed_sum/cpp/libcvrp.so"
#LIB_PATH = "/home/kpempera/distributed_sum/cpp/libcvrp.so"

@ray.remote
class BestCostActor:
    """
    Actor for sharing the best found cost between workers.
    Allows for better branch pruning in real-time.
    """
    def __init__(self):
        self.best_cost = float('inf')
    
    def update(self, cost):
        """Update the best cost if a better one is found"""
        if cost < self.best_cost:
            self.best_cost = cost
            return True
        return False
    
    def get(self):
        """Get the current best cost"""
        return self.best_cost

@ray.remote
def solve_city(dist_np, C, city, BnB):
    """
    Function called by Ray worker.
    Converts numpy array -> ctypes double** on the worker.
    """
    lib = ctypes.CDLL(LIB_PATH)

    # Deklaracja sygnatury C++
    lib.solve_from_first_city.argtypes = [
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib.solve_from_first_city.restype = ctypes.c_double

    n = dist_np.shape[0]

    # Convert numpy -> double**
    c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
    for i in range(n):
        row = (ctypes.c_double * n)(*dist_np[i])
        c_mat[i] = row

    # Call C++ BnB for the first city
    return lib.solve_from_first_city(c_mat, n, C, city, BnB)


def run_distributed_bnb(n=12, C=5, BnB = 1):
    # Create random data
    coords = np.random.rand(n, 2) * 10000
    dist = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(coords[i] - coords[j])

    # Start Ray cluster
    ray.init(address="auto")

    # Create tasks for each first city (except depot 0)
    futures = [solve_city.remote(dist, C, i, BnB) for i in range(1, n)]

    # Get results
    results = ray.get(futures)
    best_global = min(results)

    print(f"Best global cost: {best_global}")


if __name__ == "__main__":
    run_distributed_bnb()
