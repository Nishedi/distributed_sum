import ray
import numpy as np
import os
from ctypes import CDLL, c_double, c_int, POINTER

def get_lib_path():
    """
    Dynamically find the library path. Tries multiple locations:
    1. Relative to this script's directory
    2. ~/distributed_sum/cpp/libsum.so
    3. /home/cluster/distributed_sum/cpp/libsum.so
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try relative path from script location
    possible_paths = [
        os.path.join(script_dir, "..", "cpp", "libsum.so"),
        os.path.expanduser("~/distributed_sum/cpp/libsum.so"),
        "/home/cluster/distributed_sum/cpp/libsum.so",
    ]
    
    for path in possible_paths:
        normalized_path = os.path.normpath(path)
        if os.path.exists(normalized_path):
            return normalized_path
    
    # If none found, raise informative error
    raise FileNotFoundError(
        f"Could not find libsum.so in any of the expected locations: {possible_paths}"
    )

def load_lib():
    lib_path = get_lib_path()
    lib = CDLL(lib_path)
    lib.sum_array.argtypes = [POINTER(c_double), c_int]
    lib.sum_array.restype = c_double
    return lib


@ray.remote
def sum_chunk(chunk: np.ndarray) -> float:
    # 🔒 worker ładuje bibliotekę lokalnie
    lib = load_lib()

    n = chunk.size
    c_array = (c_double * n)(*chunk)

    return lib.sum_array(c_array, n)


if __name__ == "__main__":
    ray.init(address="auto")

    # testowe dane
    data = np.random.rand(1_000_000).astype(np.float64)

    # liczba tasków = liczba CPU (bezpiecznie)
    num_tasks = int(ray.available_resources().get("CPU", 1))
    chunks = np.array_split(data, num_tasks)

    futures = [sum_chunk.remote(chunk) for chunk in chunks]
    partial = ray.get(futures)

    print("Suma całkowita:", sum(partial))
