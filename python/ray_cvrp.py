# python/ray_cvrp.py

import ray
import ctypes
import numpy as np
import os


def get_lib_path():
    """
    Dynamically find the library path. Tries multiple locations:
    1. Relative to this script's directory
    2. ~/distributed_sum/cpp/libcvrp.so
    3. /home/cluster/distributed_sum/cpp/libcvrp.so
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try relative path from script location
    possible_paths = [
        os.path.join(script_dir, "..", "cpp", "libcvrp.so"),
        os.path.expanduser("~/distributed_sum/cpp/libcvrp.so"),
        "/home/cluster/distributed_sum/cpp/libcvrp.so",
    ]
    
    for path in possible_paths:
        normalized_path = os.path.normpath(path)
        if os.path.exists(normalized_path):
            return normalized_path
    
    # If none found, raise informative error with normalized paths
    normalized_paths = [os.path.normpath(p) for p in possible_paths]
    raise FileNotFoundError(
        f"Could not find libcvrp.so in any of the expected locations:\n" +
        "\n".join(f"  - {p}" for p in normalized_paths)
    )


@ray.remote
def solve_city(dist_np, C, city):
    """
    Funkcja wywoływana przez Ray worker.
    Konwertuje numpy array -> ctypes double** dopiero na workerze.
    """
    lib_path = get_lib_path()
    lib = ctypes.CDLL(lib_path)

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

    # Uruchomienie Ray cluster
    ray.init(address="auto")

    # Tworzymy zadania dla każdego pierwszego miasta (oprócz startowego 0)
    futures = [solve_city.remote(dist, C, i) for i in range(1, n)]

    # Pobranie wyników
    results = ray.get(futures)
    best_global = min(results)

    print(f"Best global cost: {best_global}")


if __name__ == "__main__":
    run_distributed_bnb()
