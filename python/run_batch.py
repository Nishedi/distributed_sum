import argparse
import subprocess
import sys
import time


def run_experiments(seed):
    configs = [# 150 minut
        ("B", 10),
        ("B", 30),
        ("B", 50),
        ("B", 70),
        ("B", 90),
        ("B", 110),
        ("B", 130),
        ("B", 150),
        ("B", 170),

        ("A", 10),
        ("A", 15),
        ("A", 20),
        ("A", 25),
        ("A", 30),
        ("A", 35),
    ]

    print(f"=== Rozpoczynam serię {len(configs)} symulacji ===")
    start_time = time.time()

    for mode, n in configs:
        print(f"\n{'-' * 50}")
        print(f"URUCHAMIANIE: Mode={mode}, n={n}, seed={seed}")
        print(f"{'-' * 50}")

        cmd = [
            sys.executable, "simulation.py",
            "--mode", mode,
            "--n", str(n),
            "--seed", str(seed)
        ]

        try:
            subprocess.run(cmd, check=True)

        except subprocess.CalledProcessError as e:
            print(f"[BŁĄD] Symulacja (Mode={mode}, n={n}) zakończyła się błędem!")
        except KeyboardInterrupt:
            print("\n[PRZERWANO] Użytkownik przerwał serię eksperymentów.")
            sys.exit(1)

    total_duration = time.time() - start_time
    print(f"\n{'-' * 50}")
    print(f"ZAKOŃCZONO WSZYSTKIE SYMULACJE.")
    print(f"Całkowity czas trwania serii: {total_duration:.2f} s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CVRP Day Simulator")
    parser.add_argument("--seed", type=int, default=1, help="Seed dla uruchomienia")
    for i in range(27, 30):
        run_experiments(i)
