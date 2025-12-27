import ray
import numpy as np
import os
from ctypes import CDLL, c_double, c_int, POINTER

LIB_PATH = os.path.join("/home/cluster/distributed_sum/cpp/libsum.so")

def load_lib():
    lib = CDLL(LIB_PATH)
    lib.sum_array.argtypes = [POINTER(c_double), c_int]
    lib.sum_array.restype = c_double
    return lib


@ray.remote(max_retries=3, retry_exceptions=True)
def sum_chunk(chunk: np.ndarray) -> float:
    # 🔒 worker ładuje bibliotekę lokalnie
    lib = load_lib()

    n = chunk.size
    c_array = (c_double * n)(*chunk)

    return lib.sum_array(c_array, n)


if __name__ == "__main__":
    ray.init(
        address="auto",
        ignore_reinit_error=True,
        _temp_dir="/tmp/ray"
    )

    # testowe dane
    data = np.random.rand(1_000_000).astype(np.float64)

    # liczba tasków = liczba CPU (bezpiecznie)
    num_tasks = int(ray.available_resources().get("CPU", 1))
    chunks = np.array_split(data, num_tasks)

    futures = [sum_chunk.remote(chunk) for chunk in chunks]
    
    # Pobranie wyników z obsługą błędów
    partial = []
    for i, future in enumerate(futures):
        try:
            result = ray.get(future)
            partial.append(result)
        except Exception as e:
            print(f"Warning: Task {i} failed with error: {e}. Skipping...")
            continue
    
    if partial:
        print("Suma całkowita:", sum(partial))
        print(f"Ukończono {len(partial)} z {len(futures)} zadań")
    else:
        print("Błąd: Wszystkie zadania nie powiodły się!")
