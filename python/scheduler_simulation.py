# import ray
# import time
# import numpy as np
# import argparse
# import csv
# import os
# from dataclasses import dataclass, field
# from typing import List, Dict
# from queue import Queue
#
# # Import your existing solver logic
# from ray_cvrp import solve_whole_instance_node_parallel, solve_city_pair_active_sync, BoundTracker
# from greedy import greedy_cvrp_1nn  # Assuming this exists based on your imports, otherwise we can mock it
#
#
# # --- KONFIGURACJA SYMULACJI ---
#
# @dataclass
# class Task:
#     id: int
#     n: int  # Liczba miast (trudność)
#     C: int  # Pojemność
#     seed: int  # Seed dla powtarzalności instancji
#     arrival_time: float  # Czas w sekundach od startu symulacji, kiedy zadanie trafia do kolejki
#
#     # Metryki (wypełniane po wykonaniu)
#     start_time: float = 0.0
#     finish_time: float = 0.0
#
#     @property
#     def wait_time(self):
#         return max(0.0, self.start_time - self.arrival_time)
#
#     @property
#     def service_time(self):
#         return self.finish_time - self.start_time
#
#     @property
#     def turnaround_time(self):
#         return self.finish_time - self.arrival_time
#
#
# class WorkloadGenerator:
#     @staticmethod
#     def generate_instance_data(n, seed):
#         """Generuje dane instancji deterministycznie na podstawie seeda."""
#         np.random.seed(seed)
#         coords = np.random.rand(n, 2) * 10000
#         dist = np.zeros((n, n))
#         for i in range(n):
#             for j in range(n):
#                 dist[i, j] = np.linalg.norm(coords[i] - coords[j])
#         return dist
#
#     @staticmethod
#     def create_scenario(scenario_type: str, num_tasks: int, base_n: int, seed_start: int):
#         tasks = []
#         current_arrival = 0.0
#
#         print(f"Generowanie scenariusza: {scenario_type.upper()}")
#
#         if scenario_type == "steady":
#             # Stały napływ: Zadania pojawiają się co X sekund
#             # Dobieramy interwał tak, by system się nie "zatkał" natychmiast, ale miał co robić
#             interval = 2.0
#             for i in range(num_tasks):
#                 tasks.append(Task(id=i, n=base_n, C=5, seed=seed_start + i, arrival_time=current_arrival))
#                 current_arrival += interval
#
#         elif scenario_type == "burst":
#             # Burst: Wszystkie zadania wpadają niemal naraz na początku
#             for i in range(num_tasks):
#                 tasks.append(Task(id=i, n=base_n, C=5, seed=seed_start + i, arrival_time=current_arrival))
#                 current_arrival += 0.1  # Bardzo krótki odstęp
#
#         elif scenario_type == "straggler":
#             # Straggler: Małe zadania, jedno OGROMNE w środku, potem małe
#             # Zadanie 0-3: Małe
#             # Zadanie 4: Straggler (duże N)
#             # Zadanie 5-9: Małe
#             for i in range(num_tasks):
#                 difficulty = base_n
#                 if i == num_tasks // 2:  # Środkowe zadanie to Straggler
#                     difficulty = base_n + 4  # Znacznie trudniejsze (w CVRP n+4 to wykładniczy skok)
#                     print(f" -> Zadanie {i} będzie 'Stragglerem' (n={difficulty})")
#
#                 tasks.append(Task(id=i, n=difficulty, C=5, seed=seed_start + i, arrival_time=current_arrival))
#                 current_arrival += 1.0
#
#         return tasks
#
#
# # --- SILNIKI WYKONAWCZE (SCHEDULERY) ---
#
# def run_approach_a_cluster_exclusive(tasks: List[Task], sync_iters=1000, sync_time=2000):
#     """
#     Podejście A: Cluster Multi-thread.
#     Strategia: Latency-Oriented.
#     FIFO. Pobiera jedno zadanie, rzuca na nie CAŁY klaster (wszystkie pary miast), czeka na wynik, bierze następne.
#     Blokuje kolejkę, ale rozwiązuje pojedyncze zadanie bardzo szybko.
#     """
#     results = []
#     simulation_start_real = time.time()
#
#     # Kolejka zadań oczekujących (symulacja przyjścia)
#     queue = Queue()
#     next_task_idx = 0
#     total_tasks = len(tasks)
#
#     print(f"\n[A] Start symulacji Cluster Exclusive (Latency). Liczba zadań: {total_tasks}")
#
#     processed_count = 0
#
#     while processed_count < total_tasks:
#         current_sim_time = time.time() - simulation_start_real
#
#         # 1. Sprawdź czy nadeszły nowe zadania
#         while next_task_idx < total_tasks and tasks[next_task_idx].arrival_time <= current_sim_time:
#             print(
#                 f" [t={current_sim_time:.2f}s] Zadanie {tasks[next_task_idx].id} (n={tasks[next_task_idx].n}) wpadło do kolejki.")
#             queue.put(tasks[next_task_idx])
#             next_task_idx += 1
#
#         # 2. Jeśli mamy zadanie i klaster jest wolny (w tym podejściu zawsze jest "wolny" jak skończył poprzednie)
#         if not queue.empty():
#             task = queue.get()
#
#             # Rejestracja startu
#             task.start_time = time.time() - simulation_start_real
#             print(f" [t={task.start_time:.2f}s] Uruchamianie zadania {task.id} na całym klastrze...")
#
#             # --- LOGIKA ROZWIĄZYWANIA (Z Ray Cvrp) ---
#             dist = WorkloadGenerator.generate_instance_data(task.n, task.seed)
#             _, greedy_cost = greedy_cvrp_1nn(dist, task.C)
#             initial_bound = int(greedy_cost)
#
#             # Tworzymy Tracker dla TEGO konkretnego zadania
#             tracker = BoundTracker.remote(initial_bound)
#
#             # Generujemy pod-zadania (pary miast) - to zajmuje cały klaster
#             futures = []
#             for i in range(1, task.n):
#                 for j in range(1, task.n):
#                     if i != j:
#                         # options(num_cpus=1) zapewnia że worker bierze 1 CPU,
#                         # więc przy wielu parach zajmiemy wszystkie rdzenie klastra
#                         f = solve_city_pair_active_sync.options(num_cpus=1).remote(
#                             dist, task.C, i, j, 1, initial_bound, tracker, sync_iters, sync_time
#                         )
#                         futures.append(f)
#
#             # Czekamy na WSZYSTKIE pary (Barrier)
#             _ = ray.get(futures)
#
#             # Pobieramy ostateczny wynik
#             final_cost = ray.get(tracker.get_bound.remote())
#             # -----------------------------------------
#
#             task.finish_time = time.time() - simulation_start_real
#             print(
#                 f" [t={task.finish_time:.2f}s] Zadanie {task.id} zakończone. Koszt: {final_cost}. Czas obsługi: {task.service_time:.2f}s")
#             results.append(task)
#             processed_count += 1
#
#         else:
#             # Brak zadań w kolejce, czekamy na nadejście
#             time.sleep(0.1)
#
#     return results
#
#
# def run_approach_b_node_parallel(tasks: List[Task], max_concurrent_tasks=4):
#     """
#     Podejście B: Node-Instance Isolation.
#     Strategia: Throughput-Oriented.
#     Każde zadanie dostaje 1 CPU i liczy się niezależnie.
#     Nie blokujemy kolejki - jeśli są wolne sloty (CPU), bierzemy kolejne zadanie.
#     """
#     results = []
#     simulation_start_real = time.time()
#
#     queue = Queue()
#     next_task_idx = 0
#     total_tasks = len(tasks)
#
#     # Śledzenie aktywnych zadań: słownik {future: task_object}
#     active_futures = {}
#
#     print(f"\n[B] Start symulacji Node Parallel (Throughput). Max concurrency: {max_concurrent_tasks}")
#
#     while len(results) < total_tasks:
#         current_sim_time = time.time() - simulation_start_real
#
#         # 1. Sprawdź czy nadeszły nowe zadania
#         while next_task_idx < total_tasks and tasks[next_task_idx].arrival_time <= current_sim_time:
#             print(
#                 f" [t={current_sim_time:.2f}s] Zadanie {tasks[next_task_idx].id} (n={tasks[next_task_idx].n}) wpadło do kolejki.")
#             queue.put(tasks[next_task_idx])
#             next_task_idx += 1
#
#         # 2. Sprawdź czy coś się zakończyło
#         if active_futures:
#             # ray.wait zwraca zakończone (ready) i niezakończone (not_ready)
#             # timeout=0 oznacza sprawdzenie natychmiastowe bez blokowania
#             ready_ids, not_ready_ids = ray.wait(list(active_futures.keys()), num_returns=len(active_futures), timeout=0)
#
#             for r_id in ready_ids:
#                 task = active_futures.pop(r_id)
#                 task.finish_time = time.time() - simulation_start_real
#                 cost = ray.get(r_id)  # Pobranie wyniku
#                 print(
#                     f" [t={task.finish_time:.2f}s] Zadanie {task.id} zakończone. Koszt: {cost}. Czas obsługi: {task.service_time:.2f}s")
#                 results.append(task)
#
#         # 3. Jeśli są wolne sloty i zadania w kolejce -> Uruchom
#         while len(active_futures) < max_concurrent_tasks and not queue.empty():
#             task = queue.get()
#
#             task.start_time = time.time() - simulation_start_real
#             print(f" [t={task.start_time:.2f}s] Przypisywanie zadania {task.id} do wolnego wątku...")
#
#             # --- LOGIKA ROZWIĄZYWANIA (Node Parallel) ---
#             dist = WorkloadGenerator.generate_instance_data(task.n, task.seed)
#             _, greedy_cost = greedy_cvrp_1nn(dist, task.C)
#             initial_bound = int(greedy_cost)
#
#             # Uruchamiamy CAŁĄ instancję na jednym workerze
#             future = solve_whole_instance_node_parallel.options(num_cpus=1).remote(
#                 dist, task.C, 1, initial_bound
#             )
#             # --------------------------------------------
#
#             active_futures[future] = task
#
#         # Krótki sleep, żeby nie spalić CPU pętlą while (symulacja czasu)
#         time.sleep(0.1)
#
#     return results
#
#
# def save_simulation_results(filename, scenario_name, method_name, results: List[Task]):
#     file_exists = os.path.isfile(filename)
#     with open(filename, mode="a", newline="") as f:
#         writer = csv.writer(f)
#         if not file_exists:
#             writer.writerow(["scenario", "method", "task_id", "n", "arrival_ts", "start_ts", "finish_ts", "wait_time",
#                              "service_time", "turnaround_time"])
#
#         for t in results:
#             writer.writerow([
#                 scenario_name,
#                 method_name,
#                 t.id,
#                 t.n,
#                 f"{t.arrival_time:.4f}",
#                 f"{t.start_time:.4f}",
#                 f"{t.finish_time:.4f}",
#                 f"{t.wait_time:.4f}",
#                 f"{t.service_time:.4f}",
#                 f"{t.turnaround_time:.4f}"
#             ])
#
#
# def print_summary(results: List[Task]):
#     avg_wait = np.mean([t.wait_time for t in results])
#     avg_service = np.mean([t.service_time for t in results])
#     avg_turnaround = np.mean([t.turnaround_time for t in results])
#     makespan = max([t.finish_time for t in results])
#
#     print("-" * 40)
#     print(f"RAPORT KOŃCOWY")
#     print("-" * 40)
#     print(f"Makespan (Całkowity czas): {makespan:.4f} s")
#     print(f"Średni czas oczekiwania (Queue): {avg_wait:.4f} s")
#     print(f"Średni czas obsługi (Compute):   {avg_service:.4f} s")
#     print(f"Średni czas przejścia (Total):   {avg_turnaround:.4f} s")
#     print("-" * 40)
#
#
# # --- MAIN ---
#
# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="HPC Scheduler Simulation for CVRP")
#     parser.add_argument("--scenario", type=str, default="steady", choices=["steady", "burst", "straggler"],
#                         help="Typ ruchu zadań")
#     parser.add_argument("--tasks", type=int, default=5, help="Liczba zadań w scenariuszu")
#     parser.add_argument("--n", type=int, default=13, help="Bazowy rozmiar problemu (liczba miast)")
#     parser.add_argument("--method", type=str, default="A", choices=["A", "B"],
#                         help="A=ClusterExclusive (Latency), B=NodeParallel (Throughput)")
#     parser.add_argument("--cpus", type=int, default=4, help="Liczba dostępnych slotów dla metody B")
#     parser.add_argument("--out", type=str, default="simulation_results.csv", help="Plik wynikowy")
#
#     args = parser.parse_args()
#
#     # Inicjalizacja Ray
#     ray.init(address="auto", ignore_reinit_error=True)
#
#     # 1. Generowanie scenariusza
#     tasks = WorkloadGenerator.create_scenario(args.scenario, args.tasks, args.n, seed_start=42)
#
#     # 2. Uruchomienie wybranego schedulera
#     if args.method == "A":
#         processed_tasks = run_approach_a_cluster_exclusive(tasks)
#         method_full_name = "Approach A (Latency)"
#     else:
#         processed_tasks = run_approach_b_node_parallel(tasks, max_concurrent_tasks=args.cpus)
#         method_full_name = "Approach B (Throughput)"
#
#     # 3. Zapis i raport
#     save_simulation_results(args.out, args.scenario, method_full_name, processed_tasks)
#     print_summary(processed_tasks)

import ray
import time
import numpy as np
import argparse
import csv
import os
from dataclasses import dataclass, field
from typing import List, Dict
from queue import Queue


from ray_cvrp import solve_whole_instance_node_parallel, solve_city_pair_active_sync, BoundTracker
from greedy import greedy_cvrp_1nn

@dataclass
class Task:
    id: int
    n: int
    C: int
    seed: int
    arrival_time: float

    start_time: float = 0.0
    finish_time: float = 0.0

    @property
    def wait_time(self):
        return max(0.0, self.start_time - self.arrival_time)

    @property
    def service_time(self):
        return self.finish_time - self.start_time

    @property
    def turnaround_time(self):
        return self.finish_time - self.arrival_time


class WorkloadGenerator:
    @staticmethod
    def generate_instance_data(n, seed):
        np.random.seed(seed)
        coords = np.random.rand(n, 2) * 10000
        dist = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                dist[i, j] = np.linalg.norm(coords[i] - coords[j])
        return dist

    @staticmethod
    def get_difficulty_distribution(num_tasks, dist_type, n_min, n_max, seed):
        np.random.seed(seed)

        if dist_type == "constant":
            return [n_min] * num_tasks

        elif dist_type == "uniform":
            return np.random.randint(n_min, n_max + 1, num_tasks).tolist()

        elif dist_type == "skewed_easy":
            samples = []
            for _ in range(num_tasks):
                if np.random.random() < 0.8:
                    n = np.random.randint(n_min, n_min + 2)
                else:
                    n = np.random.randint(n_min + 2, n_max + 1)
                samples.append(n)
            return samples

        elif dist_type == "skewed_hard":
            return np.random.randint(n_max - 2, n_max + 1, num_tasks).tolist()

        return [n_min] * num_tasks

    @staticmethod
    def create_scenario(arrival_pattern: str, dist_type: str, num_tasks: int, n_min: int, n_max: int, seed_start: int,
                        malicious_idx: int = -1):
        tasks = []
        current_arrival = 0.0

        difficulties = WorkloadGenerator.get_difficulty_distribution(num_tasks, dist_type, n_min, n_max, seed_start)

        if malicious_idx >= 0 and malicious_idx < num_tasks:
            difficulties[malicious_idx] = n_max + 3
            print(f" -> WSTRZYKNIĘTO ZADANIE ZŁOŚLIWE: ID={malicious_idx}, N={difficulties[malicious_idx]}")

        print(f"Generowanie scenariusza: Pattern={arrival_pattern.upper()}, Diff={dist_type.upper()}")

        for i in range(num_tasks):
            n = difficulties[i]

            if arrival_pattern == "steady":
                tasks.append(Task(id=i, n=n, C=5, seed=seed_start + i, arrival_time=current_arrival))
                current_arrival += 3.0

            elif arrival_pattern == "rapid":
                tasks.append(Task(id=i, n=n, C=5, seed=seed_start + i, arrival_time=current_arrival))
                current_arrival += 0.5

            elif arrival_pattern == "burst":
                tasks.append(Task(id=i, n=n, C=5, seed=seed_start + i, arrival_time=current_arrival))
                current_arrival += 0.05

        return tasks



def run_approach_a_cluster_exclusive(tasks: List[Task], sync_iters=1000, sync_time=2000):
    results = []
    simulation_start_real = time.time()
    queue = Queue()
    next_task_idx = 0
    total_tasks = len(tasks)

    print(f"\n[A] Start symulacji Cluster Exclusive (Latency). Zadania: {total_tasks}")
    processed_count = 0

    while processed_count < total_tasks:
        current_sim_time = time.time() - simulation_start_real
        while next_task_idx < total_tasks and tasks[next_task_idx].arrival_time <= current_sim_time:
            queue.put(tasks[next_task_idx])
            next_task_idx += 1

        if not queue.empty():
            task = queue.get()
            task.start_time = time.time() - simulation_start_real
            print(f" [t={task.start_time:.2f}s] Start Task {task.id} (n={task.n})...")

            dist = WorkloadGenerator.generate_instance_data(task.n, task.seed)
            _, greedy_cost = greedy_cvrp_1nn(dist, task.C)
            initial_bound = int(greedy_cost)
            tracker = BoundTracker.remote(initial_bound)

            futures = []
            for i in range(1, task.n):
                for j in range(1, task.n):
                    if i != j:
                        f = solve_city_pair_active_sync.options(num_cpus=1).remote(
                            dist, task.C, i, j, 1, initial_bound, tracker, sync_iters, sync_time
                        )
                        futures.append(f)
            _ = ray.get(futures)  # Barrier

            task.finish_time = time.time() - simulation_start_real
            print(f" [t={task.finish_time:.2f}s] Koniec Task {task.id}. Czas: {task.service_time:.2f}s")
            results.append(task)
            processed_count += 1
        else:
            time.sleep(0.1)
    return results


def run_approach_b_node_parallel(tasks: List[Task], max_concurrent_tasks=4):
    results = []
    simulation_start_real = time.time()
    queue = Queue()
    next_task_idx = 0
    total_tasks = len(tasks)
    active_futures = {}

    print(f"\n[B] Start symulacji Node Parallel (Throughput). Max concurrency: {max_concurrent_tasks}")

    while len(results) < total_tasks:
        current_sim_time = time.time() - simulation_start_real

        while next_task_idx < total_tasks and tasks[next_task_idx].arrival_time <= current_sim_time:
            queue.put(tasks[next_task_idx])
            next_task_idx += 1

        if active_futures:
            ready_ids, _ = ray.wait(list(active_futures.keys()), num_returns=len(active_futures), timeout=0)
            for r_id in ready_ids:
                task = active_futures.pop(r_id)
                task.finish_time = time.time() - simulation_start_real
                print(f" [t={task.finish_time:.2f}s] Koniec Task {task.id}. Czas: {task.service_time:.2f}s")
                results.append(task)

        while len(active_futures) < max_concurrent_tasks and not queue.empty():
            task = queue.get()
            task.start_time = time.time() - simulation_start_real
            print(f" [t={task.start_time:.2f}s] Start Task {task.id} (n={task.n}) na wątku...")

            dist = WorkloadGenerator.generate_instance_data(task.n, task.seed)
            _, greedy_cost = greedy_cvrp_1nn(dist, task.C)
            initial_bound = int(greedy_cost)

            future = solve_whole_instance_node_parallel.options(num_cpus=1).remote(
                dist, task.C, 1, initial_bound
            )
            active_futures[future] = task

        time.sleep(0.1)
    return results


def save_simulation_results(filename, scenario_info, method_name, results: List[Task]):
    file_exists = os.path.isfile(filename)
    with open(filename, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["scenario", "method", "task_id", "n", "arrival_ts", "start_ts", "finish_ts", "wait_time",
                             "service_time", "turnaround_time"])

        for t in results:
            writer.writerow([
                scenario_info,
                method_name,
                t.id,
                t.n,
                f"{t.arrival_time:.4f}",
                f"{t.start_time:.4f}",
                f"{t.finish_time:.4f}",
                f"{t.wait_time:.4f}",
                f"{t.service_time:.4f}",
                f"{t.turnaround_time:.4f}"
            ])


def print_summary(results: List[Task]):
    avg_wait = np.mean([t.wait_time for t in results])
    avg_service = np.mean([t.service_time for t in results])
    avg_turnaround = np.mean([t.turnaround_time for t in results])
    makespan = max([t.finish_time for t in results])

    print("-" * 40)
    print(f"Makespan: {makespan:.4f} s")
    print(f"Avg Wait: {avg_wait:.4f} s")
    print(f"Avg Turnaround: {avg_turnaround:.4f} s")
    print("-" * 40)




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HPC Scheduler Simulation for CVRP")


    parser.add_argument("--pattern", type=str, default="steady", choices=["steady", "rapid", "burst"],
                        help="Wzorzec napływu zadań w czasie")


    parser.add_argument("--dist", type=str, default="constant",
                        choices=["constant", "uniform", "skewed_easy", "skewed_hard"],
                        help="Rozkład trudności (N)")
    parser.add_argument("--n_min", type=int, default=12, help="Minimalne N")
    parser.add_argument("--n_max", type=int, default=14, help="Maksymalne N")


    parser.add_argument("--malicious_at", type=int, default=-1,
                        help="Indeks zadania, które ma być outlierem (np. 5). -1 oznacza brak.")

    # Ogólne
    parser.add_argument("--tasks", type=int, default=10, help="Liczba zadań")
    parser.add_argument("--method", type=str, default="A", choices=["A", "B"],
                        help="Metoda A (Latency) lub B (Throughput)")
    parser.add_argument("--cpus", type=int, default=8, help="Workerzy dla metody B")
    parser.add_argument("--out", type=str, default="simulation_results_v2.csv", help="Plik wynikowy")

    args = parser.parse_args()

    ray.init(address="auto", ignore_reinit_error=True)

    # 1. Tworzenie scenariusza z nowymi parametrami
    tasks = WorkloadGenerator.create_scenario(
        arrival_pattern=args.pattern,
        dist_type=args.dist,
        num_tasks=args.tasks,
        n_min=args.n_min,
        n_max=args.n_max,
        seed_start=42,
        malicious_idx=args.malicious_at
    )

    # Nazwa scenariusza do CSV (łączona z parametrów)
    scenario_tag = f"{args.pattern}_{args.dist}"
    if args.malicious_at >= 0:
        scenario_tag += "_malicious"

    # 2. Uruchomienie
    if args.method == "A":
        processed_tasks = run_approach_a_cluster_exclusive(tasks)
        method_name = "A_Cluster_Latency"
    else:
        processed_tasks = run_approach_b_node_parallel(tasks, max_concurrent_tasks=args.cpus)
        method_name = f"B_Node_Throughput_{args.cpus}CPU"

    # 3. Zapis
    save_simulation_results(args.out, scenario_tag, method_name, processed_tasks)
    print_summary(processed_tasks)