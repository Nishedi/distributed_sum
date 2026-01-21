import simpy
import random
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Literal

# --- KONFIGURACJA SYMULACJI ---
RANDOM_SEED = 42
NUM_CORES = 8  # Rozmiar klastra
PARALLEL_EFFICIENCY = 0.85  # Dla Podejścia A: efektywność zrównoleglenia (1.0 = idealna)
BASE_PROCESSING_SPEED = 1.0  # Modyfikator czasu bazowego


@dataclass
class Task:
    id: int
    size: int
    arrival_time: float
    start_time: float = 0.0
    finish_time: float = 0.0

    @property
    def difficulty(self):
        return (self.size ** 2.5) * 0.001


class ClusterSimulation:
    def __init__(self, env, strategy: Literal['A', 'B']):
        self.env = env
        self.strategy = strategy
        # Zasób klastra: w strategii B to pula wątków, w A to jeden "wielki" zasób
        self.cluster = simpy.Resource(env, capacity=NUM_CORES if strategy == 'B' else 1)
        self.results = []
        self.tasks_queue = []

    def calculate_runtime(self, task: Task):
        base_time = task.difficulty * BASE_PROCESSING_SPEED

        if self.strategy == 'A':
            # Podejście A: Wszystkie zasoby na jedno zadanie
            # Czas = czas na 1 wątku / (liczba rdzeni * efektywność)
            speedup = NUM_CORES * PARALLEL_EFFICIENCY
            return base_time / speedup
        else:
            # Podejście B: Jeden wątek na jedno zadanie
            # Czas = czas na 1 wątku (brak narzutu komunikacji, ale brak przyspieszenia)
            return base_time

    def process_task(self, task: Task):
        task.arrival_time = self.env.now

        # Logika kolejkowania i dostępu do zasobów
        with self.cluster.request() as req:
            yield req  # Czekaj na dostępność zasobu (kolejka)

            task.start_time = self.env.now
            runtime = self.calculate_runtime(task)

            # Symulacja przetwarzania (blokowanie zasobu na czas obliczeń)
            yield self.env.timeout(runtime)

            task.finish_time = self.env.now
            self.record_metrics(task, runtime)

    def record_metrics(self, task: Task, runtime: float):
        wait_time = task.start_time - task.arrival_time
        turnaround_time = task.finish_time - task.arrival_time

        self.results.append({
            "Scenario": None,  # Uzupełniane później
            "Strategy": f"Approach {self.strategy}",
            "Task ID": task.id,
            "Size": task.size,
            "Service Time": round(runtime, 4),
            "Wait Time": round(wait_time, 4),
            "Turnaround Time": round(turnaround_time, 4)
        })


# --- GENERATORY RUCHU (SCENARIUSZE) ---

def generator_steady_state(env, cluster: ClusterSimulation, count=50):
    """Stały, umiarkowany napływ średnich zadań."""
    for i in range(count):
        size = random.randint(12, 16)  # Średnie instancje CVRP
        task = Task(id=i, size=size, arrival_time=env.now)
        env.process(cluster.process_task(task))
        # Odstęp między zadaniami (umiarkowane obciążenie)
        yield env.timeout(random.uniform(0.5, 2.0))


def generator_burst_traffic(env, cluster: ClusterSimulation, count=50):
    """Nagły skok liczby zgłoszeń (Batch processing)."""
    # 1. Faza ciszy
    yield env.timeout(1)
    # 2. BURST: Wszystkie zadania wpadają w bardzo krótkim czasie
    for i in range(count):
        size = random.randint(10, 17)
        task = Task(id=i, size=size, arrival_time=env.now)
        env.process(cluster.process_task(task))
        yield env.timeout(random.uniform(0.01, 0.05))  # Bardzo mały odstęp


def generator_straggler_effect(env, cluster: ClusterSimulation, count=20):
    """Strumień prostych zadań zablokowany przez jedno gigantyczne."""
    for i in range(count):
        # W połowie generujemy "Stragglera" (bardzo trudne zadanie)
        if i == count // 2:
            size = 80  # Bardzo duża instancja (wysoka złożoność)
            print(f"   [!] ({env.now:.2f}s) STRAGGLER (Size {size}) enters the queue...")
        else:
            size = random.randint(10, 13)  # Małe, szybkie zadania

        task = Task(id=i, size=size, arrival_time=env.now)
        env.process(cluster.process_task(task))
        yield env.timeout(0.2)  # Szybki napływ


# --- FUNKCJA URUCHAMIAJĄCA ---

def run_experiment(scenario_name, generator_func, task_count=30):
    print(f"\n--- Running Scenario: {scenario_name} ---")
    scenario_results = []

    for strategy in ['A', 'B']:
        # Reset środowiska dla każdego podejścia
        random.seed(RANDOM_SEED)
        env = simpy.Environment()
        cluster_sim = ClusterSimulation(env, strategy)

        # Uruchomienie generatora
        env.process(generator_func(env, cluster_sim, count=task_count))

        # Start symulacji (uruchamiamy aż wszystkie procesy się zakończą)
        env.run()

        # Zbieranie wyników
        df = pd.DataFrame(cluster_sim.results)
        df['Scenario'] = scenario_name

        # Obliczanie Makespan (czas zakończenia ostatniego zadania)
        makespan = df['Turnaround Time'].max()  # Uproszczenie dla symulacji startującej od 0

        print(f"Strategy {strategy}: Tasks={len(df)}, Makespan={makespan:.2f}s")
        scenario_results.append(df)

    return pd.concat(scenario_results)


# --- MAIN ---

if __name__ == "__main__":
    all_data = []

    # 1. Steady State
    df_steady = run_experiment("Steady State", generator_steady_state, task_count=5)
    all_data.append(df_steady)

    # 2. Burst Traffic
    df_burst = run_experiment("Burst Traffic", generator_burst_traffic, task_count=5)
    all_data.append(df_burst)

    # 3. Straggler Effect
    # Mniejsza liczba zadań, żeby efekt był wyraźny w logach
    df_straggler = run_experiment("Straggler Effect", generator_straggler_effect, task_count=1)
    all_data.append(df_straggler)

    # --- AGREGACJA WYNIKÓW I RAPORTOWANIE ---
    full_df = pd.concat(all_data)

    # Grupowanie i obliczanie metryk
    summary = full_df.groupby(['Scenario', 'Strategy']).agg({
        'Wait Time': 'mean',
        'Service Time': 'mean',
        'Turnaround Time': 'mean',  # Czas przejścia (Wait + Service)
        'Task ID': 'count'  # Liczba wykonanych zadań
    }).rename(columns={'Task ID': 'Tasks Completed'})

    # Dodanie Makespan (dla każdej grupy osobno trzeba by wyciągnąć max finish time,
    # tutaj przybliżymy to przez max Turnaround Time + arrival time pierwszego,
    # ale dla uproszczenia tabeli wyświetlimy średnie).

    print("\n" + "=" * 60)
    print("FINAL RESULTS SUMMARY")
    print("=" * 60)
    print(summary)

    # Zapis do CSV do dalszej analizy (np. wykresy)
    full_df.to_csv("simulation_results.csv", index=False)
    print("\nSzczegółowe wyniki zapisano do 'simulation_results.csv'")

    # Weryfikacja tezy o Straggler Effect
    straggler_data = full_df[full_df['Scenario'] == 'Straggler Effect']
    print("\n--- Straggler Effect Analysis ---")
    for strat in ['Approach A', 'Approach B']:
        subset = straggler_data[straggler_data['Strategy'] == strat]
        max_wait = subset['Wait Time'].max()
        avg_wait = subset['Wait Time'].mean()
        print(f"{strat}: Max Wait Time = {max_wait:.2f}s, Avg Wait Time = {avg_wait:.2f}s")