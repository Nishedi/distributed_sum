import time
import argparse
import numpy as np
import ray
import csv
import heapq
from datetime import datetime, timedelta
import collections

from greedy import greedy_cvrp_1nn
from ray_cvrp import (
    solve_city_pair_active_sync,
    solve_whole_instance_node_parallel,
    BoundTracker
)

SIM_START_HOUR = 8
SIM_END_HOUR = 18
TOTAL_SIM_HOURS = SIM_END_HOUR - SIM_START_HOUR
REAL_MIN_TO_SIM_HOUR = 1.0

class Task:
    def __init__(self, task_id, arrival_time_offset, difficulty_level, n, C):
        self.id = task_id
        self.arrival_time_offset = arrival_time_offset
        self.n = n
        self.C = C
        self.difficulty = difficulty_level

        self.coords = np.random.rand(n, 2) * 10000
        self.dist = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                self.dist[i, j] = np.linalg.norm(self.coords[i] - self.coords[j])

        _, greedy_cost = greedy_cvrp_1nn(self.dist, C)
        self.initial_bound = int(greedy_cost)

        self.start_time = None
        self.end_time = None
        self.status = "PENDING"
        self.best_cost = float('inf')

    # def __lt__(self, other):
    #     prio_map = {"hard": 0, "medium": 1, "easy": 2}
    #     my_prio = prio_map[self.difficulty]
    #     other_prio = prio_map[other.difficulty]
    #
    #     if my_prio != other_prio:
    #         return my_prio < other_prio
    #     return self.arrival_time_offset < other.arrival_time_offset
    def __lt__(self, other):# priorytet po przybyciu
        return self.arrival_time_offset < other.arrival_time_offset


def format_sim_time(seconds_from_start):
    base_time = datetime(2024, 1, 1, SIM_START_HOUR, 0, 0)
    current_time = base_time + timedelta(seconds=seconds_from_start)
    return current_time.strftime("%H:%M:%S")


def generate_schedule(n_tasks_per_hour, total_hours, seed = 42):
    np.random.seed(seed)
    tasks = []
    task_counter = 0

    # 60% Easy (11-12), 30% Medium (13-14), 10% Hard (15-16)
    probs = [0.5, 0.32, 0.18, 0]
    types = ["easy", "medium", "hard", "very hard"]

    ranges = {
        "easy": (11, 13),
        "medium": (13, 15),
        "hard": (15, 16),
        "very hard": (16,17)
    }

    seconds_per_hour = 3600

    for h in range(total_hours):
        count = n_tasks_per_hour

        for _ in range(count):
            offset_in_hour = np.random.randint(0, seconds_per_hour)
            total_offset = (h * seconds_per_hour) + offset_in_hour

            t_type = np.random.choice(types, p=probs)
            n_min, n_max = ranges[t_type]
            n = np.random.randint(n_min, n_max)

            task = Task(task_counter, total_offset, t_type, n, C=5)
            tasks.append(task)
            task_counter += 1
    if tasks:
        num_very_hard = np.random.randint(0, 3)

        indices_to_replace = np.random.choice(len(tasks), num_very_hard, replace=False)
        for idx in indices_to_replace:
            original_task = tasks[idx]

            vh_type = "very hard"
            vh_min, vh_max = ranges[vh_type]
            vh_n = np.random.randint(vh_min, vh_max)

            tasks[idx] = Task(original_task.id, original_task.arrival_time_offset, vh_type, vh_n, C=5)

    tasks.sort(key=lambda x: x.arrival_time_offset)
    return tasks


def run_simulation(args):
    ray.init(address="auto", ignore_reinit_error=True)

    tasks_per_hour = args.n
    mode = args.mode
    simulation_speed_scale = 60.0 / args.speed

    time_factor = (3600.0) / (args.speed * 60.0)

    print(f"--- START SYMULACJI ---")
    print(f"Tryb: {mode}")
    print(f"Godziny pracy: {SIM_START_HOUR}:00 - {SIM_END_HOUR}:00")
    print(f"Zadań na godzinę: {tasks_per_hour}")
    print(f"Skalowanie czasu: 1 min realna = {args.speed} h symulacyjna")

    all_tasks = generate_schedule(tasks_per_hour, TOTAL_SIM_HOURS, args.seed)
    print(f"Wygenerowano łącznie {len(all_tasks)} zadań na cały dzień.")

    task_queue = []
    active_tasks = {}
    completed_tasks = []

    start_real_time = time.time()
    next_task_idx = 0

    total_cpus = int(ray.cluster_resources().get("CPU", 1))

    csv_file = f"sim_results_{mode}_{tasks_per_hour}tph.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["task_id", "difficulty", "n", "arrival_sim", "start_sim", "end_sim", "status", "cost",
                         "real_duration_sec", "waiting_time_mili_sec", "time_in_system_mili_sec"])

    try:
        while True:
            elapsed_real = time.time() - start_real_time
            elapsed_sim = elapsed_real * time_factor

            current_sim_time_str = format_sim_time(elapsed_sim)

            if elapsed_sim >= TOTAL_SIM_HOURS * 3600:
                print(f"\n[{current_sim_time_str}] KONIEC DNIA PRACY (18:00).")
                break

            while next_task_idx < len(all_tasks):
                task = all_tasks[next_task_idx]
                if task.arrival_time_offset <= elapsed_sim:
                    heapq.heappush(task_queue, task)
                    print(
                        f"[{current_sim_time_str}] NOWE ZADANIE: ID={task.id} Trudność={task.difficulty} (n={task.n})")
                    next_task_idx += 1
                else:
                    break

            if mode == "A":
                if not active_tasks and task_queue:
                    current_task = heapq.heappop(task_queue)

                    print(f"   -> [{current_sim_time_str}] START Zadania {current_task.id} {current_task.difficulty} (Mode A - Cluster)")
                    current_task.start_time = elapsed_sim
                    current_task.start_real = time.time()
                    current_task.status = "RUNNING"

                    tracker = BoundTracker.remote(current_task.initial_bound)
                    futures = []
                    for i in range(1, current_task.n):
                        for j in range(1, current_task.n):
                            if i != j:
                                f = solve_city_pair_active_sync.remote(
                                    current_task.dist, current_task.C, i, j, 1,
                                    current_task.initial_bound, tracker,
                                    args.sync_iters, args.sync_time
                                )
                                futures.append(f)

                    active_tasks[current_task.id] = {
                        "task": current_task,
                        "futures": futures
                    }

            elif mode == "B":
                active_count = len(active_tasks)
                free_slots = total_cpus - active_count

                while free_slots > 0 and task_queue:
                    current_task = heapq.heappop(task_queue)

                    print(
                        f"   -> [{current_sim_time_str}] START Zadania {current_task.id} {current_task.difficulty}(Mode B - Slot {active_count + 1}/{total_cpus})")
                    current_task.start_time = elapsed_sim
                    current_task.start_real = time.time()
                    current_task.status = "RUNNING"

                    f = solve_whole_instance_node_parallel.options(num_cpus=1).remote(
                        current_task.dist, current_task.C, 1, current_task.initial_bound
                    )

                    active_tasks[current_task.id] = {
                        "task": current_task,
                        "futures": [f]
                    }

                    free_slots -= 1
                    active_count += 1

            tasks_to_remove = []

            for t_id, data in active_tasks.items():
                futures = data["futures"]
                task = data["task"]

                ready, not_ready = ray.wait(futures, num_returns=len(futures), timeout=0)

                if len(not_ready) == 0:
                    results_raw = ray.get(ready)

                    if mode == "A":
                        costs = [r[0] for r in results_raw]
                        best = min(costs)
                    else:
                        best = results_raw[0]

                    task.end_time = elapsed_sim
                    real_duration = time.time() - task.start_real
                    task.best_cost = best
                    task.status = "COMPLETED"

                    print(
                        f" [OK] [{current_sim_time_str}] KONIEC Zadania {task.id}.{task.difficulty}. Koszt: {best:.2f}. Czas (sim): {(task.end_time - task.start_time) / 60:.1f} min. "
                        f"Czas w systemie: {(task.end_time-task.arrival_time_offset)/60:.1f}, Czas pojawienia sie: {format_sim_time(task.arrival_time_offset)}")

                    with open(csv_file, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            task.id, task.difficulty, task.n,
                            format_sim_time(task.arrival_time_offset),
                            format_sim_time(task.start_time),
                            format_sim_time(task.end_time),
                            "COMPLETED", best, f"{real_duration*1000:.1f}", f"{(task.start_time - task.arrival_time_offset):.2f}", f"{(task.end_time - task.arrival_time_offset):.2f}"
                        ])

                    tasks_to_remove.append(t_id)

            for t_id in tasks_to_remove:
                del active_tasks[t_id]

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nPrzerwano symulację ręcznie.")

    print("\n--- RAPORT KOŃCOWY ---")

    for t_id, data in active_tasks.items():
        task = data["task"]
        print(f"Zadanie {task.id} ({task.difficulty}) przerwane o 18:00.")
        with open(csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                task.id, task.difficulty, task.n,
                format_sim_time(task.arrival_time_offset),
                format_sim_time(task.start_time),
                "18:00:00",
                "UNFINISHED", -1, -1, -1
            ])

    while task_queue:
        task = heapq.heappop(task_queue)
        print(f"Zadanie {task.id} ({task.difficulty}) nie doczekało się realizacji.")
        with open(csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                task.id, task.difficulty, task.n,
                format_sim_time(task.arrival_time_offset),
                "-", "-",
                "IGNORED", -1, -1
            ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CVRP Day Simulator")
    parser.add_argument("--n", type=int, default=5, help="Średnia liczba zadań na godzinę")
    parser.add_argument("--mode", type=str, choices=["A", "B"], required=True,
                        help="A: Cluster/Latency, B: Node/Throughput")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Ile godzin symulacyjnych przypada na 1 minutę rzeczywistą (default 1.0)")
    parser.add_argument("--sync_iters", type=int, default=1000)
    parser.add_argument("--sync_time", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42, help="Seed dla generatora losowego")

    args = parser.parse_args()

    run_simulation(args)