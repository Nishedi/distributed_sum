import pandas as pd
import matplotlib
matplotlib.use("tkAgg")
import matplotlib.pyplot as plt
import glob
import re
import os


def analyze_and_plot():
    files = glob.glob("sim_results_*_*tph.csv")

    results = []

    print(f"Znaleziono plików: {len(files)}")

    for filename in files:
        match = re.search(r"sim_results_([AB])_(\d+)tph\.csv", filename)

        if match:
            mode = match.group(1)
            tph = int(match.group(2))

            try:
                df = pd.read_csv(filename)

                df_completed = df[df['status'] == 'COMPLETED']

                if not df_completed.empty:
                    p95 = df_completed['time_in_system_mili_sec'].quantile(0.95)

                    results.append({
                        "Mode": mode,
                        "TPH": tph,
                        "P95": p95
                    })
            except Exception as e:
                print(f"Błąd przy odczycie {filename}: {e}")


    res_df = pd.DataFrame(results)

    if res_df.empty:
        print("Brak danych do wyrysowania.")
        return

    res_df = res_df.sort_values(by=['Mode', 'TPH'])
    print("\nWyliczone wartości centyla 0.95:")
    print(res_df)

    plt.figure(figsize=(10, 6))

    data_a = res_df[res_df['Mode'] == 'A']
    if not data_a.empty:
        plt.plot(data_a['TPH'], data_a['P95'], marker='o', label='Podejście A (Cluster - Latency)')


    data_b = res_df[res_df['Mode'] == 'B']
    if not data_b.empty:
        plt.plot(data_b['TPH'], data_b['P95'], marker='s', label='Podejście B (Node - Throughput)')

    plt.xlabel('Częstotliwość napływu zadań (Zadania/h)')
    plt.ylabel('95. Centyl czasu w systemie [s]')
    plt.title('Zależność 95. centyla czasu obsługi od obciążenia')
    plt.legend()
    plt.grid(True)

    output_filename = 'wykres_centyl_95_arch.png'
    plt.savefig(output_filename)
    print(f"\nWykres zapisano jako: {output_filename}")
    plt.show()


if __name__ == "__main__":
    analyze_and_plot()