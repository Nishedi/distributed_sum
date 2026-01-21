import ray
import time
import numpy as np
import argparse
import csv
import os
import random
from dataclasses import dataclass, field
from queue import PriorityQueue
from typing import List

# Import solverów z istniejących plików
from ray_cvrp import solve_whole_instance_node_parallel, solve_city_pair_active_sync, BoundTracker
from greedy import greedy_cvrp_1nn


@dataclass(order=True)
class Task:
    # PriorityQueue w Pythonie sortuje rosnąco.
    # Żeby priorytetyzować TRUDNE (duże N), jako priorytet ustawiamy -N (ujemne N).
    priority: int

    id: int = field(compare=False)
    n: int = field(compare=False)
    C: int = field(compare=False)
    seed: int = field(compare=False)

    # Czas symulacyjny (godziny, np. 8.5 to 8:30)
    sim_arrival_hour: float = field(compare=False)

    # Czas rzeczywisty (sekundy od startu skryptu)
    real_arrival_time: float = field(compare=False, default=0.0)

    # Metryki
    real_start_time: float = field(compare=False, default=0.0)
    real_finish_time: float = field(compare=False, default=0.0)
    completed_on_time: bool = field(compare=False, default=True)

    @property
    def service_time(self):
        return self.real_finish_time - self.real_start_time


class DayWorkloadGenerator:
    @staticmethod
    def generate_day_schedule(
            tasks_per_hour: int,
            start_hour: int,
            end_hour: int,
            sim_hour_duration_sec: float,
            probs: dict,
            seed: int
    ):
        """Generuje harmonogram na cały dzień z góry."""
        np.random.seed(seed)
        random.seed(seed)

        tasks = []
        task_counter = 0

        # Definicje zakresów trudności
        ranges = {
            "easy": (11, 12),
            "medium": (13, 14),
            "hard": (15, 16)
        }

        # Iterujemy po każdej godzinie pracy (np. 8, 9, ..., 17)
        for h in range(start_hour, end_hour):
            for _ in range(tasks_per_hour):
                # 1. Losowanie trudności zgodnie z zadanym procentem
                r = random.random()
                if r < probs['easy']:
                    cat = "easy"
                elif r < probs['easy'] + probs['medium']:
                    cat = "medium"
                else:
                    cat = "hard"

                n = random.randint(ranges[cat][0], ranges[cat][1])

                # 2. Losowanie czasu wewnątrz godziny (np. 8:15, 8:43)
                # Offset w godzinach (0.0 - 1.0)
                minute_offset = random.random()
                sim_arrival = h + minute_offset

                # Przeliczenie na czas rzeczywisty, w którym skrypt ma "wpuścić" zadanie
                # Czas 0.0 w symulacji to start_hour
                real_arrival = (sim_arrival - start_hour) * sim_hour_duration_sec

                # Priorytet: -n (żeby największe N schodziły pierwsze)
                t = Task(
                    priority=-n,
                    id=task_counter,
                    n=n,
                    C=5,
                    seed=seed + task_counter,
                    sim_arrival_hour=sim_arrival,
                    real_arrival_time=real_arrival
                )
                tasks.append(t)
                task_counter += 1

        # Sortujemy zadania po czasie przyjścia, żeby symulator brał je chronologicznie
        tasks.sort(key=lambda x: x.real_arrival_time)
        return tasks

    @staticmethod
    def generate_instance_data(n, seed):
        np.random.seed(seed)
        coords = np.random.rand(n, 2) * 10000
        dist = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                dist[i, j] = np.linalg.norm(coords[i] - coords[j])
        return dist


def format_sim_time(sim_hour):
    """Konwertuje 8.5 -> '08:30'"""
    h = int(sim_hour)
    m = int((sim_hour - h) * 60)
    return f"{h:02d}:{m:02d}"


# --- SYMULATOR ---

@ray.remote
def solve_method_A_full_cluster(dist, n, C, initial_bound, sync_iters=1000, sync_time=2000):
    """
    LOGIKA TESTU 8A (Cluster Multi-thread).
    To zadanie działa jako orkiestrator. Nie zajmuje CPU obliczeniowego (num_cpus=0),
    ale spawnuje setki pod-zadań (pary miast), które zajmują CAŁY klaster.
    """
    # 1. Lokalny tracker (tak jak w Test 8A)
    tracker = BoundTracker.remote(initial_bound)
    futures = []

    # 2. Generowanie par (Sub-tasks)
    # options(num_cpus=1) -> każde pod-zadanie bierze 1 rdzeń
    # Ponieważ par jest N*(N-1) (np. 150+), zajmą wszystkie rdzenie w klastrze natychmiast.
    for i in range(1, n):
        for j in range(1, n):
            if i != j:
                f = solve_city_pair_active_sync.options(num_cpus=1).remote(
                    dist, C, i, j, 1, initial_bound, tracker, sync_iters, sync_time
                )
                futures.append(f)

    # 3. Synchronizacja - czekamy aż WSZYSTKIE pary skończą
    # To blokuje ten orkiestrator, ale Ray w tle wykonuje pary na workerach.
    ray.get(futures)

    # 4. Pobranie wyniku
    final_cost = ray.get(tracker.get_bound.remote())
    return final_cost


# --- GŁÓWNA PĘTLA SYMULACJI ---

def run_day_simulation(
        tasks: List[Task],
        method: str,
        sim_hour_duration: float,
        start_hour: int,
        end_hour: int,
        cpus_for_b: int = 4
):
    results = []
    queue = PriorityQueue()
    active_futures = {}

    total_tasks = len(tasks)
    next_task_idx = 0
    start_time_real = time.time()

    # LIMIT WSPÓŁBIEŻNOŚCI (Kluczowa różnica A vs B)
    if method == "A":
        # Podejście A: 1 Zadanie = Cały klaster.
        # Nie pozwalamy na więcej niż 1 zadanie główne naraz.
        max_concurrent_tasks = 1
    else:
        # Podejście B: Izolacja.
        # Pozwalamy na tyle zadań, ile mamy CPU.
        max_concurrent_tasks = cpus_for_b

    print(f"\nSTART SYMULACJI [{method}]")
    print(f"Max Concurrent Tasks: {max_concurrent_tasks}")
    print(f"Godziny pracy: {start_hour}:00 - {end_hour}:00 (Ratio: 1h = {sim_hour_duration}s)")
    print("-" * 60)

    while len(results) < total_tasks:
        now_real = time.time() - start_time_real
        current_sim_hour = start_hour + (now_real / sim_hour_duration)

        # 1. ARRIVAL: Nowe zadania wpadają do kolejki
        while next_task_idx < total_tasks and tasks[next_task_idx].real_arrival_time <= now_real:
            task = tasks[next_task_idx]
            print(
                f" [{format_sim_time(task.sim_arrival_hour)}] NOWE: ID#{task.id} (N={task.n}) -> Kolejka (Rozmiar: {queue.qsize() + 1})")
            queue.put(task)
            next_task_idx += 1

        # 2. FINISH: Odbiór wyników
        if active_futures:
            # Sprawdzamy co się skończyło
            ready_ids, _ = ray.wait(list(active_futures.keys()), num_returns=len(active_futures), timeout=0)

            for r_id in ready_ids:
                task = active_futures.pop(r_id)
                task.real_finish_time = time.time() - start_time_real

                # Czy zdążył przed fajrantem?
                finish_sim_hour = start_hour + (task.real_finish_time / sim_hour_duration)
                task.completed_on_time = (finish_sim_hour <= end_hour)
                status = "OK" if task.completed_on_time else "PO GODZINACH"

                print(
                    f"   -> KONIEC: ID#{task.id} o {format_sim_time(finish_sim_hour)}. Czas: {task.service_time:.2f}s. [{status}]")
                results.append(task)

        # 3. SCHEDULING: Uruchamianie nowych zadań
        # Sprawdzamy czy mamy wolny "slot" (dla A slot jest jeden na cały klaster!)
        while len(active_futures) < max_concurrent_tasks and not queue.empty():
            task = queue.get()

            task.real_start_time = time.time() - start_time_real
            start_sim_hour = start_hour + (task.real_start_time / sim_hour_duration)

            print(f" [START] ID#{task.id} (N={task.n}) o {format_sim_time(start_sim_hour)}...")

            # Generowanie danych
            dist = DayWorkloadGenerator.generate_instance_data(task.n, task.seed)
            _, greedy_cost = greedy_cvrp_1nn(dist, task.C)
            initial_bound = int(greedy_cost)

            if method == "A":
                # --- PODEJŚCIE A: PEŁNY KLASTER ---
                # Uruchamiamy orkiestratora. Dajemy num_cpus=0 dla orkiestratora,
                # żeby nie blokował slotu, bo on sam tylko odpala pod-zadania.
                # Pod-zadania (pary) zjedzą cały klaster (num_cpus=1 każde).
                future = solve_method_A_full_cluster.options(num_cpus=0).remote(
                    dist, task.n, task.C, initial_bound
                )
                active_futures[future] = task

            else:
                # --- PODEJŚCIE B: IZOLACJA (NODE PARALLEL) ---
                # 1 instancja = 1 CPU.
                future = solve_whole_instance_node_parallel.options(num_cpus=1).remote(
                    dist, task.C, 1, initial_bound
                )
                active_futures[future] = task

        time.sleep(0.05)  # Loop throttling

    return results

def save_day_results(filename, tasks: List[Task], method_name):
    file_exists = os.path.isfile(filename)
    with open(filename, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "method", "task_id", "n",
                "sim_arrival", "sim_finish", "status",
                "real_wait_s", "real_service_s"
            ])

        for t in tasks:
            sim_finish_hour = (t.real_finish_time / (
                        t.real_finish_time / t.real_finish_time)) if t.real_finish_time == 0 else 0  # safety
            # Odtwarzamy sim_finish na podstawie real
            # sim_duration = real_duration / ratio
            sim_finish = t.sim_arrival_hour + (t.turnaround_time / (
                t.turnaround_time / (t.real_finish_time - t.real_arrival_time) if t.turnaround_time > 0 else 1))
            # Prościej:
            # start_hour to np 8.
            # real_time 60s = 1h
            sim_finish_h = 8 + (
                        t.real_finish_time / 60.0)  # Tu trzeba wziąć ratio z argumentów, ale do CSV zapiszmy surowe dane

            status_str = "OK" if t.completed_on_time else "LATE"

            writer.writerow([
                method_name, t.id, t.n,
                f"{format_sim_time(t.sim_arrival_hour)}",
                status_str,
                f"{t.completed_on_time}",
                f"{t.real_start_time - t.real_arrival_time:.2f}",  # Wait
                f"{t.service_time:.2f}"  # Service
            ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Symulacja dnia pracy logistyki (CVRP)")

    parser.add_argument("--tasks_per_hour", type=int, default=5, help="Ile zadań wpada średnio w ciągu godziny")
    parser.add_argument("--method", type=str, default="A", choices=["A", "B"], help="Strategia")
    parser.add_argument("--sim_hour_duration", type=float, default=60.0, help="Ile sekund rzeczywistych trwa 1 godzina symulacji")
    parser.add_argument("--workday_start", type=int, default=8, help="Godzina rozpoczęcia (np. 8)")
    parser.add_argument("--workday_end", type=int, default=18, help="Godzina zakończenia (np. 18)")

    parser.add_argument("--p_easy", type=float, default=0.6, help="Prawdopodobieństwo łatwych (11-12)")
    parser.add_argument("--p_medium", type=float, default=0.3, help="Prawdopodobieństwo średnich (13-14)")

    parser.add_argument("--cpus", type=int, default=64, help="Liczba workerów dla metody B")
    parser.add_argument("--out", type=str, default="day_results.csv")

    args = parser.parse_args()

    # ray.init(address="auto", ignore_reinit_error=True)

    p_hard = 1.0 - args.p_easy - args.p_medium
    if p_hard < 0:
        print("Błąd: Suma prawdopodobieństw > 1.0")
        exit(1)

    probs = {"easy": args.p_easy, "medium": args.p_medium, "hard": p_hard}
    print(f"Rozkład trudności: Easy={probs['easy']:.2f}, Medium={probs['medium']:.2f}, Hard={probs['hard']:.2f}")

    tasks = DayWorkloadGenerator.generate_day_schedule(
        tasks_per_hour=args.tasks_per_hour,
        start_hour=args.workday_start,
        end_hour=args.workday_end,
        sim_hour_duration_sec=args.sim_hour_duration,
        probs=probs,
        seed=42
    )

    print(f"Wygenerowano {len(tasks)} zadań na dzień {args.workday_start}:00-{args.workday_end}:00.")
    for task in tasks:
        print(task)

    # # 3. Uruchomienie symulacji
    # completed_tasks = run_day_simulation(
    #     tasks,
    #     args.method,
    #     args.sim_hour_duration,
    #     args.workday_start,
    #     args.workday_end,
    #     cpus_for_b=args.cpus
    # )
    #
    # # 4. Statystyki końcowe
    # ok_count = sum(1 for t in completed_tasks if t.completed_on_time)
    # late_count = len(completed_tasks) - ok_count
    # print(f"Wynik dnia: {ok_count} zadań wykonanych w terminie, {late_count} spóźnionych.")
    #
    # # Zapis
    # save_day_results(args.out, completed_tasks, f"{args.method}_DaySim")