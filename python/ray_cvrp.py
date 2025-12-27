# python/ray_cvrp.py

import ray
import ctypes
import numpy as np
import os

# Ścieżka absolutna do biblioteki C++
LIB_PATH = "/home/cluster/distributed_sum/cpp/libcvrp.so"


@ray.remote(max_retries=3, retry_exceptions=True)
def solve_city(dist_np, C, city):
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
    return lib.solve_from_first_city(c_mat, n, C, city)


def run_distributed_bnb(n=12, C=5):
    # Tworzenie losowych danych
    coords = np.random.rand(n, 2) * 10000
    dist = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(coords[i] - coords[j])

    # Uruchomienie Ray cluster z konfiguracją odporności na awarie
    ray.init(
        address="auto",
        ignore_reinit_error=True,
        _temp_dir="/tmp/ray"
    )

    # Tworzymy zadania dla każdego pierwszego miasta (oprócz startowego 0)
    futures = [solve_city.remote(dist, C, i) for i in range(1, n)]

    # Pobranie wyników z obsługą błędów
    results = []
    for future in futures:
        try:
            result = ray.get(future)
            results.append(result)
        except Exception as e:
            print(f"Warning: Task failed with error: {e}. Skipping...")
            continue
    
    if not results:
        print("Error: All tasks failed!")
        return None
    
    best_global = min(results)

    print(f"Best global cost: {best_global}")
    return best_global


if __name__ == "__main__":
    run_distributed_bnb()
