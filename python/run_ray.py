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
from ray_cvrp import solve_city, solve_city_pair, BoundTracker

ray.init(address="auto")
np.random.seed(42)
n = 14
C = 5

# dane testowe
coords = np.random.rand(n, 2) * 10000
dist = np.zeros((n, n))
results = []

for i in range(n):
    for j in range(n):
        dist[i, j] = np.linalg.norm(coords[i] - coords[j])

route, cost = greedy_cvrp_1nn(dist, C=5)
print("Długość trasy:", cost)
print(f"Liczba węzłów: {n}")
print(f"Pojemność pojazdu: {C}")
print()
# Warm-up run to load libraries
futures = [solve_city.remote(dist, C, i, 1, 999999999) for i in range(1, min(3, n))]

# Test 1: BnB without shared bound (original)
print("=== Test 1: BnB bez współdzielonego ograniczenia ===")
start_time = time.time()
futures = [solve_city.remote(dist, C, i, 1, 999999999) for i in range(1, n)]
results = ray.get(futures)
end_time = time.time()-start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print()


# Test 2: BnB_SP without shared bound (original)
print("=== Test 2: BnB_SP bez współdzielonego ograniczenia ===")
start_time = time.time()
futures = [solve_city.remote(dist, C, i, 1, int(cost)) for i in range(1, n)]
results = ray.get(futures)
end_time = time.time()-start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print()

# Test 3: BnB with shared bound tracker (IMPROVED)
print("=== Test 3: BnB ze współdzielonym ograniczeniem (POPRAWIONY) ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(999999999)
futures = [solve_city.remote(dist, C, i, 1, 999999999, bound_tracker) for i in range(1, n)]
results = ray.get(futures)
end_time = time.time()-start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print()

# Test 4: BnB_SP with shared bound tracker (IMPROVED)
print("=== Test 4: BnB_SP ze współdzielonym ograniczeniem (POPRAWIONY) ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(int(cost))
futures = [solve_city.remote(dist, C, i, 1, int(cost), bound_tracker) for i in range(1, n)]
results = ray.get(futures)
end_time = time.time()-start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print()

# Test 5: Fine-grained task distribution with city pairs (IMPROVED)
print("=== Test 5: BnB z drobnymi zadaniami (pary miast) - NAJBARDZIEJ POPRAWIONY ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(int(cost))
# Create tasks for pairs of cities for better load balancing
futures = [solve_city_pair.remote(dist, C, i, j, 1, int(cost), bound_tracker) 
           for i in range(1, n) for j in range(1, n) if i != j]

results = ray.get(futures)
end_time = time.time()-start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print(f"Liczba zadań: {len(futures)}")
print()

#start_time = time.time()
#futures = [solve_city.remote(dist, C, i, 0, 999999999) for i in range(1, n)]
#results = ray.get(futures)
#end_time = time.time()-start_time

#print("BF Najlepszy wynik:", min(results), " w czasie:", end_time)


