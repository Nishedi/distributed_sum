import subprocess
import sys
import time
import os


OUTPUT_FILE = "benchmark_results_final.csv"

TASKS_COUNT = 10
N_MIN = 11
N_MAX = 16
CPUS_FOR_B = 64


experiments = []

for pattern in ["steady", "rapid", "burst"]:
    experiments.append({
        "desc": f"Experiment 1: Arrival Impact - {pattern.upper()} (Method A)",
        "args": [
            "--pattern", pattern,
            "--dist", "constant",
            "--n_min", str(N_MIN),
            "--tasks", str(TASKS_COUNT),
            "--method", "A",
            "--out", OUTPUT_FILE
        ]
    })
    experiments.append({
        "desc": f"Experiment 1: Arrival Impact - {pattern.upper()} (Method B)",
        "args": [
            "--pattern", pattern,
            "--dist", "constant",
            "--n_min", str(N_MIN),
            "--tasks", str(TASKS_COUNT),
            "--method", "B",
            "--cpus", str(CPUS_FOR_B),
            "--out", OUTPUT_FILE
        ]
    })

for dist in ["uniform", "skewed_easy", "skewed_hard"]:
    # Metoda A
    experiments.append({
        "desc": f"Experiment 2: Variance - {dist.upper()} (Method A)",
        "args": [
            "--pattern", "rapid",
            "--dist", dist,
            "--n_min", str(N_MIN),
            "--n_max", str(N_MAX),
            "--tasks", str(TASKS_COUNT),
            "--method", "A",
            "--out", OUTPUT_FILE
        ]
    })
    experiments.append({
        "desc": f"Experiment 2: Variance - {dist.upper()} (Method B)",
        "args": [
            "--pattern", "rapid",
            "--dist", dist,
            "--n_min", str(N_MIN),
            "--n_max", str(N_MAX),
            "--tasks", str(TASKS_COUNT),
            "--method", "B",
            "--cpus", str(CPUS_FOR_B),
            "--out", OUTPUT_FILE
        ]
    })


malicious_idx = "4"
experiments.append({
    "desc": "Experiment 3: Malicious Task (Method A)",
    "args": [
        "--pattern", "steady",
        "--dist", "constant",
        "--n_min", str(N_MIN),
        "--tasks", str(TASKS_COUNT),
        "--malicious_at", malicious_idx,
        "--method", "A",
        "--out", OUTPUT_FILE
    ]
})
experiments.append({
    "desc": "Experiment 3: Malicious Task (Method B)",
    "args": [
        "--pattern", "steady",
        "--dist", "constant",
        "--n_min", str(N_MIN),
        "--tasks", str(TASKS_COUNT),
        "--malicious_at", malicious_idx,
        "--method", "B",
        "--cpus", str(CPUS_FOR_B),
        "--out", OUTPUT_FILE
    ]
})

def run_benchmarks():
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        print(f"Usunięto stary plik wyników: {OUTPUT_FILE}")

    total_exps = len(experiments)
    print(f"=== ROZPOCZYNANIE PEŁNEGO BENCHMARKU ({total_exps} testów) ===")
    start_time = time.time()

    for i, exp in enumerate(experiments):
        print(f"\n[{i + 1}/{total_exps}] {exp['desc']}")
        print("-" * 60)

        cmd = [sys.executable, "scheduler_simulation.py"] + exp['args']

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"!!! BŁĄD podczas wykonywania eksperymentu: {exp['desc']}")
            print(e)

        time.sleep(2)

    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"BENCHMARK ZAKOŃCZONY. Czas całkowity: {total_time:.2f}s")
    print("=" * 60)

    print("\nURUCHAMIANIE ANALIZY WYNIKÓW...")
    if os.path.exists("analyze_results.py"):
        subprocess.run([sys.executable, "analyze_results.py", OUTPUT_FILE])
    else:
        print("Nie znaleziono pliku analyze_results.py. Pomięto generowanie wykresów.")


if __name__ == "__main__":
    run_benchmarks()