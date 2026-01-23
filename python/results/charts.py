# import pandas as pd
# import matplotlib
# matplotlib.use("tkAgg")
# import matplotlib.pyplot as plt
# import glob
# import re
# import os
#
#
# def analyze_and_plot():
#     files = glob.glob("sim_results_*_*tph.csv")
#
#     results = []
#
#     print(f"Znaleziono plików: {len(files)}")
#
#     for filename in files:
#         # match = re.search(r"sim_results_([AB])_(\d+)_Seed(\d+)tph\.csv", filename)
#         match = re.search(r"sim_results_([AB])_(\d+)_Seed2tph\.csv", filename)
#         if match:
#             mode = match.group(1)
#             tph = int(match.group(2))
#
#             try:
#                 df = pd.read_csv(filename)
#
#                 df_completed = df[df['status'] == 'COMPLETED']
#
#                 if not df_completed.empty:
#                     p95 = df_completed['time_in_system_mili_sec'].quantile(0.95)
#
#                     results.append({
#                         "Mode": mode,
#                         "TPH": tph,
#                         "P95": p95
#                     })
#             except Exception as e:
#                 print(f"Błąd przy odczycie {filename}: {e}")
#
#
#     res_df = pd.DataFrame(results)
#
#     if res_df.empty:
#         print("Brak danych do wyrysowania.")
#         return
#
#     res_df = res_df.sort_values(by=['Mode', 'TPH'])
#     print("\nWyliczone wartości centyla 0.95:")
#     print(res_df)
#
#     plt.figure(figsize=(10, 6))
#
#     data_a = res_df[res_df['Mode'] == 'A']
#     if not data_a.empty:
#         plt.plot(data_a['TPH'], data_a['P95'], marker='o', label='Podejście A (Cluster - Latency)')
#
#
#     data_b = res_df[res_df['Mode'] == 'B']
#     if not data_b.empty:
#         plt.plot(data_b['TPH'], data_b['P95'], marker='s', label='Podejście B (Node - Throughput)')
#
#     plt.xlabel('Częstotliwość napływu zadań (Zadania/h)')
#     plt.ylabel('95. Centyl czasu w systemie [s]')
#     plt.title('Zależność 95. centyla czasu obsługi od obciążenia')
#     plt.legend()
#     plt.grid(True)
#
#     output_filename = '../wykres_centyl_95_arch.png'
#     plt.savefig(output_filename)
#     print(f"\nWykres zapisano jako: {output_filename}")
#     plt.show()
#
#
# if __name__ == "__main__":
#     analyze_and_plot()

import glob
import re
import pandas as pd
import matplotlib.pyplot as plt


def analyze_and_plot():
    # Pobieramy wszystkie pliki pasujące do wzorca
    files = glob.glob("sim_results_*_*tph.csv")

    results = []

    print(f"Znaleziono plików: {len(files)}")

    for filename in files:
        # ZMIANA 1: Regex teraz łapie dowolny Seed (\d+), a nie tylko 'Seed2'
        match = re.search(r"sim_results_([AB])_(\d+)_Seed(\d+)tph\.csv", filename)

        if match:
            mode = match.group(1)
            tph = int(match.group(2))
            seed = int(match.group(3))  # Opcjonalnie, jeśli chciałbyś logować seed

            try:
                df = pd.read_csv(filename)

                # Upewnij się, że kolumna istnieje (w poprzednich krokach była real_duration_sec,
                # ale tu używasz time_in_system_mili_sec - dostosuj nazwę kolumny do swojego CSV)
                target_col = 'time_in_system_mili_sec'
                if target_col not in df.columns and 'real_duration_sec' in df.columns:
                    # Fallback jeśli nazwa jest inna (dla bezpieczeństwa)
                    target_col = 'real_duration_sec'

                df_completed = df[df['status'] == 'COMPLETED']

                if not df_completed.empty:
                    # Obliczamy P95 dla TEGO KONKRETNEGO pliku (pojedynczy seed)
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

    # ZMIANA 2: Agregacja danych
    # Grupujemy po Mode i TPH, a następnie liczymy średnią z P95 (uśredniamy wyniki z różnych seedów)
    print("\nPrzed agregacją (surowe dane z każdego seeda):")
    print(res_df.head())

    res_df = res_df.groupby(['Mode', 'TPH'], as_index=False)['P95'].mean()

    # Sortowanie, żeby linie na wykresie były ciągłe
    res_df = res_df.sort_values(by=['Mode', 'TPH'])

    print("\nPo agregacji (średnia z seedów dla każdego punktu TPH):")
    print(res_df)

    # --- RYSOWANIE WYKRESU ---
    plt.figure(figsize=(10, 6))

    data_a = res_df[res_df['Mode'] == 'A']
    if not data_a.empty:
        plt.plot(data_a['TPH'], data_a['P95'], marker='o', label='Podejście A (Cluster - Latency)')

    data_b = res_df[res_df['Mode'] == 'B']
    if not data_b.empty:
        plt.plot(data_b['TPH'], data_b['P95'], marker='s', label='Podejście B (Node - Throughput)')

    plt.xlabel('Częstotliwość napływu zadań (Zadania/h)')
    plt.ylabel('Średni 95. centyl czasu w systemie [s]')  # Zaktualizowana etykieta
    plt.title('Zależność czasu obsługi od obciążenia (Uśrednione z wielu prób)')
    plt.legend()
    plt.grid(True)

    output_filename = '../wykres_centyl_95_avg_arch.png'
    plt.savefig(output_filename)
    print(f"\nWykres zapisano jako: {output_filename}")
    # plt.show() # Odkomentuj jeśli uruchamiasz lokalnie z GUI


if __name__ == "__main__":
    analyze_and_plot()