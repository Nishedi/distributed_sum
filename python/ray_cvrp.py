# python/ray_cvrp.py

import ray
import ctypes
import numpy as np
import os


# Ścieżka absolutna do biblioteki C++
LIB_PATH = "/home/cluster/distributed_sum/cpp/libcvrp.so"
#LIB_PATH = "/home/kpempera/distributed_sum/cpp/libcvrp.so"

@ray.remote
def solve_city(dist_np, C, city, BnB, bound_value):
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

    # Wywołanie C++ BnB dla pierwszego miasta
    return lib.solve_from_first_city(c_mat, n, C, city, BnB, bound_value)


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
