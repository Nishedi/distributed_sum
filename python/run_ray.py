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
        ray.init(address="auto")  # użycie klastra z resource tag
    else:
        ray.init(num_cpus=num_cpus)  # single-node

    futures = [
        solve_city.options(resources=resources).remote(dist, C, city)
        for city in first_cities
    ]

    start = time.time()
    results = ray.get(futures)
    end = time.time()

    ray.shutdown()
    best_global = min(results)
    elapsed = end - start
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
print(f"[Single node] Best cost: {best:.2f}, Time: {t:.2f}s")

# ===========================
# 2️⃣ Specific node (musisz ustawić tag resource na węźle)
# ===========================
# Przyklad:
# ray start --address=HEAD_IP:6379 --resources='{"single_node":1}'
best, t = run_experiment(dist, C, first_cities, resources={"single_node":1})
print(f"[Specific node] Best cost: {best:.2f}, Time: {t:.2f}s")

# ===========================
# 3️⃣ Full cluster
# ===========================
best, t = run_experiment(dist, C, first_cities)
print(f"[Full cluster] Best cost: {best:.2f}, Time: {t:.2f}s")
