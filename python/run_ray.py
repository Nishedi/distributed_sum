import ray
import time
import numpy as np
from ray_cvrp import solve_city, solve_city_pair, solve_city_parallel, solve_city_pair_parallel, BoundTracker
from greedy import greedy_cvrp_1nn
import argparse
import csv
import os


ray.init(address="auto")
np.random.seed(42)
parser = argparse.ArgumentParser(description="Ray CVRP BnB benchmark")
parser.add_argument("--n", type=int, default=14, help="number of cities")
parser.add_argument("--C", type=int, default=5, help="vehicle capacity")
parser.add_argument("--fn", type=str, default="results.csv", help="file name")
parser.add_argument("--ct", type=str, default="all nodes", help="single node or all nodes")
args = parser.parse_args()

n = args.n
C = args.C
ct = args.ct
csv_file = args.fn
file_exists = os.path.isfile(csv_file)
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(["n", "C", "method", "best_cost", "time_sec", "preparing_time", "computing_time", "cluster_type"])

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
preparing_time = time.time()-start_time
computing_start_time = time.time()
results = ray.get(futures)
end_time = time.time()-start_time
computing_time=time.time()-computing_start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print()
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([n, C, "Test 1: BnB bez współdzielonego ograniczenia", min(results), end_time, preparing_time, computing_time, ct])


# Test 2: BnB_SP without shared bound (original)
print("=== Test 2: BnB_SP bez współdzielonego ograniczenia ===")
start_time = time.time()
futures = [solve_city.remote(dist, C, i, 1, int(cost)) for i in range(1, n)]
preparing_time = time.time()-start_time
computing_start_time = time.time()
results = ray.get(futures)
end_time = time.time()-start_time
computing_time=time.time()-computing_start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print()
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([n, C, "Test 2: BnB_SP bez współdzielonego ograniczenia", min(results), end_time, preparing_time, computing_time, ct])

# Test 3: BnB with shared bound tracker (IMPROVED)
print("=== Test 3: BnB ze współdzielonym ograniczeniem (POPRAWIONY) ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(999999999)
futures = [solve_city.remote(dist, C, i, 1, 999999999, bound_tracker) for i in range(1, n)]
preparing_time = time.time()-start_time
computing_start_time = time.time()
results = ray.get(futures)
end_time = time.time()-start_time
computing_time=time.time()-computing_start_time
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([n, C, "Test 3: BnB ze współdzielonym ograniczeniem (POPRAWIONY)", min(results), end_time, preparing_time, computing_time, ct])

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print()

# Test 4: BnB_SP with shared bound tracker (IMPROVED)
print("=== Test 4: BnB_SP ze współdzielonym ograniczeniem (POPRAWIONY) ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(int(cost))
futures = [solve_city.remote(dist, C, i, 1, int(cost), bound_tracker) for i in range(1, n)]
preparing_time = time.time()-start_time
computing_start_time = time.time()
results = ray.get(futures)
end_time = time.time()-start_time
computing_time=time.time()-computing_start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print()
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([n, C, "Test 4: BnB_SP ze współdzielonym ograniczeniem (POPRAWIONY)", min(results), end_time, preparing_time, computing_time, ct])

# Test 5: Fine-grained task distribution with city pairs (IMPROVED)
print("=== Test 5: BnB z drobnymi zadaniami (pary miast) - NAJBARDZIEJ POPRAWIONY ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(int(cost))
# Create tasks for pairs of cities for better load balancing
futures = [solve_city_pair.remote(dist, C, i, j, 1, int(cost), bound_tracker) 
           for i in range(1, n) for j in range(1, n) if i != j]
preparing_time = time.time()-start_time
computing_start_time = time.time()
results = ray.get(futures)
end_time = time.time()-start_time
computing_time=time.time()-computing_start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print(f"Liczba zadań: {len(futures)}")
print()
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([n, C, "Test 5: BnB z drobnymi zadaniami (pary miast) - NAJBARDZIEJ POPRAWIONY", min(results), end_time, preparing_time, computing_time, ct])

# Test 6: Hybrid parallel approach with multithread per worker (NEW BEST)
print("=== Test 6: Hybrydowy BnB z wielowątkowym przetwarzaniem (MULTITHREAD+CLUSTER) ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(int(cost))
# Each Ray worker uses multiple threads (OpenMP) for internal parallelism
# This combines cluster-level and thread-level parallelism
futures = [solve_city_parallel.remote(dist, C, i, 1, int(cost), bound_tracker, num_threads=4) 
           for i in range(1, n)]
preparing_time = time.time()-start_time
computing_start_time = time.time()
results = ray.get(futures)
end_time = time.time()-start_time
computing_time=time.time()-computing_start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print(f"Liczba zadań Ray: {len(futures)}")
print(f"Wątki na zadanie: 4")
print()
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([n, C, "Test 6: Hybrydowy BnB z wielowątkowym przetwarzaniem (MULTITHREAD+CLUSTER)", min(results), end_time, preparing_time, computing_time, ct])

# Test 7: Fine-grained parallel tasks (city pairs with multithread) (ULTIMATE PERFORMANCE)
print("=== Test 7: Hybrydowy BnB z drobnymi zadaniami i wielowątkowym przetwarzaniem (ULTIMATE) ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(int(cost))
# Combines fine-grained task distribution with per-worker multithreading
# Uses fewer threads per task since there are more tasks
futures = [solve_city_pair_parallel.remote(dist, C, i, j, 1, int(cost), bound_tracker, num_threads=2) 
           for i in range(1, n) for j in range(1, n) if i != j]
preparing_time = time.time()-start_time
computing_start_time = time.time()
results = ray.get(futures)
end_time = time.time()-start_time
computing_time=time.time()-computing_start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print(f"Liczba zadań Ray: {len(futures)}")
print(f"Wątki na zadanie: 2")
print()
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([n, C, "Test 7: Hybrydowy BnB z drobnymi zadaniami i wielowątkowym przetwarzaniem (ULTIMATE)", min(results), end_time, preparing_time, computing_time, ct])

#start_time = time.time()
#futures = [solve_city.remote(dist, C, i, 0, 999999999) for i in range(1, n)]
#results = ray.get(futures)
#end_time = time.time()-start_time

#print("BF Najlepszy wynik:", min(results), " w czasie:", end_time)


