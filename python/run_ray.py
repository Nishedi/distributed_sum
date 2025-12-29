import ray
import time
import numpy as np
from ray_cvrp import solve_city

ray.init(address="auto")
np.random.seed(42)
n = 14
C = 5

# dane testowe
coords = np.random.rand(n, 2) * 10000
dist = np.zeros((n, n))

for i in range(n):
    for j in range(n):
        dist[i, j] = np.linalg.norm(coords[i] - coords[j])

# startujemy od 1..n-1
start_time = time.time()
futures = [solve_city.remote(dist, C, i, 1) for i in range(1, n)]
results = ray.get(futures)
end_time = time.time()-start_time

print("BnB Najlepszy wynik:", min(results), " w czasie:", end_time)

start_time = time.time()
futures = [solve_city.remote(dist, C, i, 0) for i in range(1, n)]
results = ray.get(futures)
end_time = time.time()-start_time

print("BF Najlepszy wynik:", min(results), " w czasie:", end_time)
