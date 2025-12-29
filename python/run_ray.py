import numpy as np

def greedy_cvrp_1nn(dist, C=5):
    n = dist.shape[0]

    visited = [False] * n
    visited[0] = True  # depot

    route = [0]
    total_cost = 0.0

    current = 0
    load = 0

    while not all(visited):
        # jeśli pojemność pełna → wracamy do depotu
        if load == C:
            total_cost += dist[current][0]
            route.append(0)
            current = 0
            load = 0
            continue

        # znajdź najbliższe nieodwiedzone miasto
        nearest = None
        nearest_dist = float("inf")

        for i in range(1, n):
            if not visited[i] and dist[current][i] < nearest_dist:
                nearest = i
                nearest_dist = dist[current][i]

        # jeśli nie ma już miast → wróć do depotu
        if nearest is None:
            total_cost += dist[current][0]
            route.append(0)
            break

        # jedziemy do miasta
        total_cost += nearest_dist
        route.append(nearest)
        visited[nearest] = True
        current = nearest
        load += 1

    # upewnij się, że kończymy w depocie
    if route[-1] != 0:
        total_cost += dist[current][0]
        route.append(0)

    return route, total_cost



import ray
import time
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

route, cost = greedy_cvrp_1nn(dist, C=5)
print("Długość trasy:", cost)
futures = [solve_city.remote(dist, C, i, 1, 999999999) for i in range(1, n)]
results = ray.get(futures)

# startujemy od 1..n-1
start_time = time.time()
futures = [solve_city.remote(dist, C, i, 1, 999999999) for i in range(1, n)]
results = ray.get(futures)
end_time = time.time()-start_time

print("BnB Najlepszy wynik:", min(results), " w czasie:", end_time)

start_time = time.time()
futures = [solve_city.remote(dist, C, i, 1, int(cost)) for i in range(1, n)]
results = ray.get(futures)
end_time = time.time()-start_time

print("BnB_SP Najlepszy wynik:", min(results), " w czasie:", end_time)

#start_time = time.time()
#futures = [solve_city.remote(dist, C, i, 0, 999999999) for i in range(1, n)]
#results = ray.get(futures)
#end_time = time.time()-start_time

#print("BF Najlepszy wynik:", min(results), " w czasie:", end_time)


