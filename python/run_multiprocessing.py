import time
import numpy as np
from multiprocessing import cpu_count
from multiprocessing_cvrp import run_distributed_bnb_mp
from greedy import greedy_cvrp_1nn
import argparse
import csv
import os


def main():
    parser = argparse.ArgumentParser(description="Multiprocessing CVRP BnB benchmark")
    parser.add_argument("--n", type=int, default=14, help="number of cities")
    parser.add_argument("--C", type=int, default=5, help="vehicle capacity")
    parser.add_argument("--fn", type=str, default="results.csv", help="file name")
    parser.add_argument("--workers", type=int, default=None, help="number of workers (default: CPU count)")
    args = parser.parse_args()

    n = args.n
    C = args.C
    num_workers = args.workers if args.workers else cpu_count()
    csv_file = args.fn
    
    print(f"=== Multiprocessing-based Distributed CVRP Benchmark ===")
    print(f"Number of cities: {n}")
    print(f"Vehicle capacity: {C}")
    print(f"Number of workers: {num_workers}")
    print(f"Results file: {csv_file}")
    print()
    
    # Initialize CSV file
    file_exists = os.path.isfile(csv_file)
    with open(csv_file, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["n", "C", "method", "best_cost", "time_sec", "workers", "cluster_type"])

    # Generate test data (use fixed seed for reproducibility)
    np.random.seed(42)
    coords = np.random.rand(n, 2) * 10000
    dist = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(coords[i] - coords[j])

    # Get greedy solution for initial bound
    print("Computing greedy solution for initial bound...")
    route, cost = greedy_cvrp_1nn(dist, C=C)
    print(f"Greedy solution cost: {cost}")
    print()

    # Test 1: Multiprocessing BnB without initial bound (coarse-grained)
    print("=== Test 1: Multiprocessing BnB bez początkowego ograniczenia (pojedyncze miasta) ===")
    start_time = time.time()
    result = run_distributed_bnb_mp(n=n, C=C, BnB=1, bound_value=999999999, 
                                     use_pairs=False, num_workers=num_workers)
    end_time = time.time() - start_time
    print(f"Najlepszy wynik: {result}")
    print(f"Czas: {end_time:.4f}s")
    print()
    with open(csv_file, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([n, C, "MP Test 1: BnB bez początkowego ograniczenia (pojedyncze miasta)", 
                        result, end_time, num_workers, "multiprocessing"])

    # Test 2: Multiprocessing BnB with greedy bound (coarse-grained)
    print("=== Test 2: Multiprocessing BnB z ograniczeniem z greedy (pojedyncze miasta) ===")
    start_time = time.time()
    result = run_distributed_bnb_mp(n=n, C=C, BnB=1, bound_value=int(cost), 
                                     use_pairs=False, num_workers=num_workers)
    end_time = time.time() - start_time
    print(f"Najlepszy wynik: {result}")
    print(f"Czas: {end_time:.4f}s")
    print()
    with open(csv_file, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([n, C, "MP Test 2: BnB z ograniczeniem z greedy (pojedyncze miasta)", 
                        result, end_time, num_workers, "multiprocessing"])

    # Test 3: Multiprocessing BnB with greedy bound (fine-grained)
    print("=== Test 3: Multiprocessing BnB z ograniczeniem z greedy (pary miast) ===")
    start_time = time.time()
    result = run_distributed_bnb_mp(n=n, C=C, BnB=1, bound_value=int(cost), 
                                     use_pairs=True, num_workers=num_workers)
    end_time = time.time() - start_time
    print(f"Najlepszy wynik: {result}")
    print(f"Czas: {end_time:.4f}s")
    print(f"Liczba zadań: {(n-1)*(n-2)}")
    print()
    with open(csv_file, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([n, C, "MP Test 3: BnB z ograniczeniem z greedy (pary miast)", 
                        result, end_time, num_workers, "multiprocessing"])

    print("=== Benchmarking completed ===")
    print(f"Results saved to: {csv_file}")


if __name__ == "__main__":
    main()
