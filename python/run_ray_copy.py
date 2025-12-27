import ray
import numpy as np
from ray_cvrp import solve_city

ray.init(address="auto")
np.random.seed(42)
n = 15
C = 5

# dane testowe
coords = np.random.rand(n, 2) * 10000
dist = np.zeros((n, n))

for i in range(n):
    for j in range(n):
        dist[i, j] = np.linalg.norm(coords[i] - coords[j])

# startujemy od 1..n-1
futures = [solve_city.remote(dist, C, i) for i in range(1, n)]
results = ray.get(futures)

print("Najlepszy wynik:", min(results))
