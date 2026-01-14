import sys

import ray
import time
import numpy as np
from ray_cvrp import solve_city, solve_city_pair, BoundTracker, solve_city_active_sync
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
parser.add_argument("--test", type=str, default="all", help="which test(s) to run: 1,2,3,4,5,6 or 'all'")
parser.add_argument("--seed", type=int, default=44, help="seed value")
parser.add_argument("--sync_iters", type=int, default=1000, help="Check sync time every X iterations")
parser.add_argument("--sync_time", type=int, default=2000, help="Sync with host every X ms")
args = parser.parse_args()

n = args.n
C = args.C
ct = args.ct
csv_file = args.fn
test_selection = args.test
sync_iters = args.sync_iters
sync_time = args.sync_time
np.random.seed(args.seed)
# Parse test selection
if test_selection.lower() == "all":
    tests_to_run = [1, 2, 3, 4, 5, 6]
else:
    try:
        tests_to_run = [int(t.strip()) for t in test_selection.split(",")]
        # Validate test numbers
        for t in tests_to_run:
            if t not in [1, 2, 3, 4, 5, 6]:
                print(f"Error: Invalid test number {t}. Must be 1-6.")
                sys.exit(1)
    except ValueError:
        print(f"Error: Invalid test selection format. Use numbers 1-6 separated by commas or 'all'")
        sys.exit(1)

print(f"Running tests: {tests_to_run}")

file_exists = os.path.isfile(csv_file)
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(["n", "C", "method", "best_cost", "time_sec", "preparing_time", "computing_time", "cluster_type"])

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
# Warm-up
futures = [solve_city.remote(dist, C, i, 1, 999999999) for i in range(1, min(3, n))]



if 1 in tests_to_run:
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

if 2 in tests_to_run:
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
if 3 in tests_to_run:
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

if 4 in tests_to_run:
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

if 5 in tests_to_run:
    # Test 5: Fine-grained task distribution with city pairs (IMPROVED)
    print("=== Test 5: BnB z drobnymi zadaniami (pary miast) - NAJBARDZIEJ POPRAWIONY ===")
    start_time = time.time()
    bound_tracker = BoundTracker.remote(int(cost))
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

if 6 in tests_to_run:
    print("=== Test 6: BnB z AKTYWNĄ synchronizacją (Callback) ===")
    start_time = time.time()

    bound_tracker = BoundTracker.remote(int(cost))

    futures = [solve_city_active_sync.remote(dist, C, i, 1, int(cost), bound_tracker, sync_iters, sync_time)
               for i in range(1, n)]

    preparing_time = time.time() - start_time
    computing_start_time = time.time()

    # Odbierz wyniki (lista krotek)
    results_raw = ray.get(futures)

    end_time = time.time() - start_time
    computing_time = time.time() - computing_start_time

    # Rozpakuj wyniki: [ (koszt1, sync1), (koszt2, sync2), ... ]
    costs = [r[0] for r in results_raw]
    syncs = [r[1] for r in results_raw]

    best_res = min(costs)
    total_syncs = sum(syncs)
    avg_syncs = total_syncs / len(syncs) if syncs else 0

    print(f"Najlepszy wynik: {best_res}")
    print(f"Czas: {end_time:.4f}s")
    print(f"Łączna liczba synchronizacji: {total_syncs}")
    print(f"Średnia liczba synchronizacji na worker: {avg_syncs:.1f}")
    print()

    with open(csv_file, mode="a", newline="") as f:
        writer = csv.writer(f)
        # Możesz dodać kolumnę total_syncs do CSV jeśli chcesz
        writer.writerow([n, C, "Test 6: BnB Sync + Callback", best_res, end_time, preparing_time, computing_time, ct])
#start_time = time.time()
#futures = [solve_city.remote(dist, C, i, 0, 999999999) for i in range(1, n)]
#results = ray.get(futures)
#end_time = time.time()-start_time

#print("BF Najlepszy wynik:", min(results), " w czasie:", end_time)


