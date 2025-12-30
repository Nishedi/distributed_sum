import ray
import time
import numpy as np
from ray_cvrp import solve_city, solve_city_pair, solve_city_batch, BoundTracker
from greedy import greedy_cvrp_1nn
import argparse
import csv
import os

# Configuration constant for batch sizing
# This determines how many tasks to create per worker for optimal load balancing
TASKS_PER_WORKER = 2.5

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

# Test 6: Batched multi-threaded approach - balanced granularity
# This approach creates fewer tasks than Test 5 but more than Test 4
# Each task processes a batch of cities, reducing communication overhead
# while maintaining good load balancing
print("=== Test 6: BnB z przetwarzaniem wsadowym (zrównoważona granulacja) - OPTYMALIZACJA KOMUNIKACJI ===")
start_time = time.time()
bound_tracker = BoundTracker.remote(int(cost))

# Calculate optimal batch size based on number of cities and available workers
# We want enough batches to balance load, but not so many that communication dominates
num_cities = n - 1  # excluding depot
num_workers = ray.available_resources().get('CPU', 4)  # default to 4 if not available
# Target: create TASKS_PER_WORKER tasks per worker for good load balancing
target_tasks = int(num_workers * TASKS_PER_WORKER)
batch_size = max(1, num_cities // target_tasks)

# Create batches of cities
batches = []
cities = list(range(1, n))
for i in range(0, len(cities), batch_size):
    batch = cities[i:i+batch_size]
    batches.append(batch)

# Create tasks for each batch
futures = [solve_city_batch.remote(dist, C, batch, 1, int(cost), bound_tracker) 
           for batch in batches]

preparing_time = time.time() - start_time
computing_start_time = time.time()
results = ray.get(futures)
end_time = time.time() - start_time
computing_time = time.time() - computing_start_time

print(f"Najlepszy wynik: {min(results)}")
print(f"Czas: {end_time:.4f}s")
print(f"Liczba zadań: {len(futures)} (batch size: {batch_size})")
print(f"Workers: {int(num_workers)}")
print()
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([n, C, "Test 6: BnB z przetwarzaniem wsadowym (zrównoważona granulacja) - OPTYMALIZACJA KOMUNIKACJI", 
                     min(results), end_time, preparing_time, computing_time, ct])

#start_time = time.time()
#futures = [solve_city.remote(dist, C, i, 0, 999999999) for i in range(1, n)]
#results = ray.get(futures)
#end_time = time.time()-start_time

#print("BF Najlepszy wynik:", min(results), " w czasie:", end_time)


