import ray
import numpy as np
from ray_cvrp import solve_city

# Uruchomienie Ray cluster z konfiguracją odporności na awarie
ray.init(
    address="auto",
    ignore_reinit_error=True,
    _temp_dir="/tmp/ray"
)

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

# Pobranie wyników z obsługą błędów
results = []
for i, future in enumerate(futures):
    try:
        result = ray.get(future)
        results.append(result)
    except Exception as e:
        print(f"Warning: Task for city {i+1} failed with error: {e}. Skipping...")
        continue

if results:
    print("Najlepszy wynik:", min(results))
    print(f"Ukończono {len(results)} z {len(futures)} zadań")
else:
    print("Błąd: Wszystkie zadania nie powiodły się!")
