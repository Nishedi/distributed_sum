# python/run_ray.py

import time
import numpy as np
import ray
from ray_cvrp import solve_city

# ===========================
# Funkcja uruchamiająca eksperyment
# ===========================
def run_experiment(dist, C, first_cities, num_cpus=None, resources=None):
    """
    dist: numpy array nxn
    C: capacity
    first_cities: lista pierwszych miast (1..n-1)
    num_cpus: jeśli chcemy ograniczyć lokalnie
    resources: jeśli chcemy wymusić taski na konkretnym węźle
    """
    if resources:
        ray.init(
            address="auto",
            ignore_reinit_error=True,
            _temp_dir="/tmp/ray"
        )
    else:
        ray.init(
            num_cpus=num_cpus,
            ignore_reinit_error=True,
            _temp_dir="/tmp/ray"
        )

    futures = [
        solve_city.options(resources=resources).remote(dist, C, city)
        if resources else solve_city.remote(dist, C, city)
        for city in first_cities
    ]

    start = time.time()
    
    # Pobranie wyników z obsługą błędów
    results = []
    for i, future in enumerate(futures):
        try:
            result = ray.get(future)
            results.append(result)
        except Exception as e:
            print(f"Warning: Task for city {first_cities[i]} failed: {e}. Skipping...")
            continue
    
    end = time.time()

    ray.shutdown()
    
    if not results:
        print("Error: All tasks failed!")
        return None, end - start
    
    best_global = min(results)
    elapsed = end - start
    print(f"Completed {len(results)}/{len(first_cities)} tasks successfully")
    return best_global, elapsed

# ===========================
# Generowanie danych testowych
# ===========================
n = 12
C = 5
coords = np.random.rand(n, 2) * 10000
dist = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        dist[i, j] = np.linalg.norm(coords[i] - coords[j])
first_cities = list(range(1, n))

# ===========================
# 1️⃣ Single-node (lokalny)
# ===========================
best, t = run_experiment(dist, C, first_cities, num_cpus=4)
if best is not None:
    print(f"[Single node] Best cost: {best:.2f}, Time: {t:.2f}s")
else:
    print(f"[Single node] Failed to complete, Time: {t:.2f}s")

# ===========================
# 2️⃣ Specific node (musisz ustawić tag resource na węźle)
# ===========================
# Przyklad:
# ray start --address=HEAD_IP:6379 --resources='{"single_node":1}'
best, t = run_experiment(dist, C, first_cities, resources={"single_node":1})
if best is not None:
    print(f"[Specific node] Best cost: {best:.2f}, Time: {t:.2f}s")
else:
    print(f"[Specific node] Failed to complete, Time: {t:.2f}s")

# ===========================
# 3️⃣ Full cluster
# ===========================
best, t = run_experiment(dist, C, first_cities)
if best is not None:
    print(f"[Full cluster] Best cost: {best:.2f}, Time: {t:.2f}s")
else:
    print(f"[Full cluster] Failed to complete, Time: {t:.2f}s")
