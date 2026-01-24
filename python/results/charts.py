import glob
import re
import pandas as pd
import matplotlib.pyplot as plt


def analyze_and_plot():
    files = glob.glob("sim_results_*_*tph.csv")

    results = []

    print(f"Znaleziono plików: {len(files)}")

    for filename in files:
        match = re.search(r"sim_results_([AB])_(\d+)_Seed(\d+)tph\.csv", filename)

        if match:
            mode = match.group(1)
            tph = int(match.group(2))
            seed = int(match.group(3))

            try:
                df = pd.read_csv(filename)
                target_col = 'time_in_system_mili_sec'
                if target_col not in df.columns and 'real_duration_sec' in df.columns:
                    target_col = 'real_duration_sec'

                df_completed = df[df['status'] == 'COMPLETED']

                if not df_completed.empty:
                    p95 = df_completed[target_col].quantile(0.95)

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

    print("\nPrzed agregacją (surowe dane z każdego seeda):")
    print(res_df.head())

    res_df = res_df.groupby(['Mode', 'TPH'], as_index=False)['P95'].mean()

    res_df = res_df.sort_values(by=['Mode', 'TPH'])

    print("\nPo agregacji (średnia z seedów dla każdego punktu TPH):")
    print(res_df)

    plt.figure(figsize=(10, 6))

    data_a = res_df[res_df['Mode'] == 'A']
    if not data_a.empty:
        plt.plot(data_a['TPH'], data_a['P95'], marker='o', label='Podejście A (Cluster - Latency)')

    data_b = res_df[res_df['Mode'] == 'B']
    if not data_b.empty:
        plt.plot(data_b['TPH'], data_b['P95'], marker='s', label='Podejście B (Node - Throughput)')

    plt.xlabel('Częstotliwość napływu zadań (Zadania/h)')
    plt.ylabel('Średni 95. centyl czasu w systemie [s]')
    plt.title('Zależność czasu obsługi od obciążenia (Uśrednione z wielu prób)')
    plt.legend()
    plt.grid(True)

    output_filename = 'wykres_centyl_95_avg_arch.png'
    plt.savefig(output_filename)
    print(f"\nWykres zapisano jako: {output_filename}")


if __name__ == "__main__":
    analyze_and_plot()