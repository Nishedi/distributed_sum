# import glob
# import pandas as pd
# import matplotlib.pyplot as plt
# import datetime
#
#
# def analyze_hourly_congestion(target_mode, target_tph):
#     file_pattern = f"sim_results_{target_mode}_{target_tph}_Seed*tph.csv"
#     files = glob.glob(file_pattern)
#
#     print(f"Analiza godzinowa dla Mode={target_mode}, TPH={target_tph}")
#     print(f"Znaleziono plików: {len(files)}")
#
#     if not files:
#         print("Nie znaleziono plików spełniających kryteria.")
#         return
#
#     all_data = []
#
#     for filename in files:
#         try:
#             df = pd.read_csv(filename)
#
#             df = df[df['status'] == 'COMPLETED'].copy()
#
#             if df.empty:
#                 continue
#
#             base_date = datetime.datetime.today().date()
#
#             df['arrival_dt'] = pd.to_datetime(df['arrival_sim'], format='%H:%M:%S').apply(
#                 lambda t: datetime.datetime.combine(base_date, t.time())
#             )
#
#             df['end_dt'] = pd.to_datetime(df['end_sim'], format='%H:%M:%S').apply(
#                 lambda t: datetime.datetime.combine(base_date, t.time())
#             )
#
#             df['system_time_sec'] = (df['end_dt'] - df['arrival_dt']).dt.total_seconds()
#
#             df['arrival_hour'] = df['arrival_dt'].dt.hour
#
#             all_data.append(df)
#
#         except Exception as e:
#             print(f"Błąd przetwarzania {filename}: {e}")
#
#     if not all_data:
#         print("Brak danych po przetworzeniu.")
#         return
#
#     full_df = pd.concat(all_data, ignore_index=True)
#     print(full_df)
#
#     hourly_stats = full_df.groupby('arrival_hour')['system_time_sec'].quantile(0.95).reset_index()
#     hourly_stats.columns = ['Hour', 'P95_System_Time']
#
#     hourly_stats = hourly_stats.sort_values('Hour')
#
#     print("\nWyniki godzinowe (95. centyl czasu w systemie [s]):")
#     print(hourly_stats)
#
#     plt.figure(figsize=(10, 6))
#
#     plt.plot(hourly_stats['Hour'], hourly_stats['P95_System_Time'],
#              marker='o', linestyle='-', linewidth=2, color='crimson', label=f'Mode {target_mode}, TPH {target_tph}')
#
#     plt.xlabel('Godzina napływu zadania (08:00 - 17:00)')
#     plt.ylabel('95. Centyl czasu w systemie [s]')
#     plt.title(f'Zator w systemie w ciągu dnia\n(Mode: {target_mode}, Obciążenie: {target_tph} zadań/h)')
#     plt.grid(True, linestyle='--', alpha=0.7)
#     plt.xticks(range(8, 19))  # Oś X co godzinę
#     plt.legend()
#
#     output_filename = f'..\\fig\\wykres_godzinowy_{target_mode}_{target_tph}.png'
#     plt.savefig(output_filename)
#     print(f"\nWykres zapisano jako: {output_filename}")
#
#
# if __name__ == "__main__":
#     analyze_hourly_congestion(target_mode="B", target_tph=30)

import glob
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import os


def analyze_hourly_congestion_avg_of_percentiles(target_mode, target_tph):
    """
    1. Dla każdego pliku (seed) liczy 95. centyl czasu w systemie na godzinę.
    2. Liczy średnią z tych centyli (uśrednia wyniki z wielu seedów).
    3. Rysuje wykres.
    """

    file_pattern = f"sim_results_{target_mode}_{target_tph}_Seed*tph.csv"
    files = glob.glob(file_pattern)

    print(f"Analiza (Średnia z Percentyli) dla Mode={target_mode}, TPH={target_tph}")
    print(f"Znaleziono plików: {len(files)}")

    if not files:
        print("Nie znaleziono plików spełniających kryteria.")
        return

    per_seed_hourly_stats = []

    for filename in files:
        try:
            df = pd.read_csv(filename)

            # Filtrujemy tylko zakończone (chyba że chcesz też analizować niedokończone jakoś inaczej)
            df = df[df['status'] == 'COMPLETED'].copy()

            if df.empty:
                continue

            # Konwersja czasów
            base_date = datetime.datetime.today().date()

            # Funkcja pomocnicza do bezpiecznego parsowania czasu
            def parse_time(t_str):
                try:
                    t = datetime.datetime.strptime(t_str, '%H:%M:%S').time()
                    return datetime.datetime.combine(base_date, t)
                except:
                    return pd.NaT

            df['arrival_dt'] = df['arrival_sim'].apply(parse_time)
            df['end_dt'] = df['end_sim'].apply(parse_time)

            # Usuwamy błędne wiersze
            df = df.dropna(subset=['arrival_dt', 'end_dt'])

            # Obliczenie czasu w systemie
            df['system_time_sec'] = (df['end_dt'] - df['arrival_dt']).dt.total_seconds()

            # Wyciągnięcie godziny
            df['arrival_hour'] = df['arrival_dt'].dt.hour

            # KROK 1: Liczymy P95 dla TEGO pliku (Seeda)
            # Wynik to Series indeksem 'arrival_hour' i wartościami P95
            seed_p95 = df.groupby('arrival_hour')['system_time_sec'].quantile(0.95)

            # Zamieniamy na DataFrame i dodajemy info o pliku (opcjonalnie)
            seed_p95_df = seed_p95.reset_index()
            seed_p95_df.columns = ['Hour', 'P95_Val']

            per_seed_hourly_stats.append(seed_p95_df)

        except Exception as e:
            print(f"Błąd przetwarzania {filename}: {e}")

    if not per_seed_hourly_stats:
        print("Brak danych po przetworzeniu.")
        return

    # Łączymy wyniki ze wszystkich seedów
    all_seeds_df = pd.concat(per_seed_hourly_stats, ignore_index=True)

    # KROK 2: Liczymy ŚREDNIĄ z tych percentyli dla każdej godziny
    final_stats = all_seeds_df.groupby('Hour')['P95_Val'].mean().reset_index()
    final_stats = final_stats.sort_values('Hour')

    print("\nWyniki końcowe (Średnia z 95. centyli z każdego seeda):")
    print(final_stats)

    # --- RYSOWANIE ---
    plt.figure(figsize=(10, 6))

    plt.plot(final_stats['Hour'], final_stats['P95_Val'],
             marker='o', linestyle='-', linewidth=2, color='blue',
             label=f'Mode {target_mode}, TPH {target_tph} (Avg of P95)')

    plt.xlabel('Godzina napływu zadania (08:00 - ...)')
    plt.ylabel('Średni 95. Centyl czasu w systemie [s]')
    plt.title(f'Zator w systemie (Metoda: Mean of Percentiles)\n(Mode: {target_mode}, TPH: {target_tph})')
    plt.grid(True, linestyle='--', alpha=0.7)

    # Ustawienie osi X na liczby całkowite
    if not final_stats.empty:
        min_h = int(final_stats['Hour'].min())
        max_h = int(final_stats['Hour'].max())
        plt.xticks(range(min_h, max_h + 1))

    plt.legend()

    output_filename = f'../fig/wykres_godzinowy_avgp95_{target_mode}_{target_tph}.png'
    plt.savefig(output_filename)
    print(f"\nWykres zapisano jako: {output_filename}")
    # plt.show()


import glob
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import os


def get_mode_stats(mode, tph):
    """
    Pomocnicza funkcja, która zwraca DataFrame ze średnimi centylami dla danego Mode.
    Zwraca None, jeśli nie znaleziono plików.
    """
    file_pattern = f"sim_results_{mode}_{tph}_Seed*tph.csv"
    files = glob.glob(file_pattern)

    print(f"   -> Szukam plików dla Mode {mode}... Znaleziono: {len(files)}")

    if not files:
        return None

    per_seed_hourly_stats = []
    base_date = datetime.datetime.today().date()

    # Funkcja do parsowania czasu
    def parse_time(t_str):
        try:
            t = datetime.datetime.strptime(t_str, '%H:%M:%S').time()
            return datetime.datetime.combine(base_date, t)
        except:
            return pd.NaT

    for filename in files:
        try:
            df = pd.read_csv(filename)
            # Analizujemy tylko COMPLETED (możesz tu zmienić logikę jeśli chcesz uwzględniać inne)
            df = df[df['status'] == 'COMPLETED'].copy()

            if df.empty:
                continue

            df['arrival_dt'] = df['arrival_sim'].apply(parse_time)
            df['end_dt'] = df['end_sim'].apply(parse_time)
            df = df.dropna(subset=['arrival_dt', 'end_dt'])

            # Czas w systemie w sekundach
            df['system_time_sec'] = (df['end_dt'] - df['arrival_dt']).dt.total_seconds()
            df['arrival_hour'] = df['arrival_dt'].dt.hour

            # KROK 1: P95 dla tego konkretnego Seeda
            seed_p95 = df.groupby('arrival_hour')['system_time_sec'].quantile(0.95).reset_index()
            seed_p95.columns = ['Hour', 'P95_Val']
            print(filename)
            print(seed_p95)

            per_seed_hourly_stats.append(seed_p95)

        except Exception as e:
            print(f"Błąd w pliku {filename}: {e}")

    if not per_seed_hourly_stats:
        return None

    # Łączymy wyniki seedów
    all_seeds_df = pd.concat(per_seed_hourly_stats, ignore_index=True)


    # KROK 2: Średnia z percentyli
    final_stats = all_seeds_df.groupby('Hour')['P95_Val'].mean().reset_index()
    return final_stats.sort_values('Hour')


def analyze_hourly_comparison(target_tph):
    """
    Główna funkcja porównująca Mode A i Mode B dla zadanego TPH.
    """
    print(f"\n=== Analiza Porównawcza (TPH={target_tph}) ===")

    # Pobieramy dane dla obu trybów
    stats_a = get_mode_stats("A", target_tph)
    stats_b = get_mode_stats("B", target_tph)

    if stats_a is None and stats_b is None:
        print("Brak danych dla obu trybów. Koniec.")
        return

    # --- RYSOWANIE ---
    plt.figure(figsize=(10, 6))

    # Rysuj A (jeśli jest)
    if stats_a is not None and not stats_a.empty:
        plt.plot(stats_a['Hour'], stats_a['P95_Val'],
                 marker='o', linestyle='-', linewidth=2, color='red',
                 label=f'Mode A (Cluster)')
        print("Dodano serię dla Mode A.")

    # Rysuj B (jeśli jest)
    if stats_b is not None and not stats_b.empty:
        plt.plot(stats_b['Hour'], stats_b['P95_Val'],
                 marker='s', linestyle='--', linewidth=2, color='blue',
                 label=f'Mode B (Node Parallel)')
        print("Dodano serię dla Mode B.")

    plt.xlabel('Godzina napływu zadania (08:00 - ...)')
    plt.ylabel('Średni 95. Centyl czasu w systemie [s]')
    plt.title(
        f'Porównanie zatorów w ciągu dnia (TPH: {target_tph})\n(Metoda: Średnia z percentyli poszczególnych symulacji)')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend()

    # Ustalanie zakresu osi X
    all_hours = []
    if stats_a is not None: all_hours.extend(stats_a['Hour'].tolist())
    if stats_b is not None: all_hours.extend(stats_b['Hour'].tolist())

    if all_hours:
        plt.xticks(range(int(min(all_hours)), int(max(all_hours)) + 1))

    output_filename = f'../fig/wykres_porownanie_A_vs_B_tph{target_tph}.png'
    plt.savefig(output_filename)
    print(f"\nWykres zapisano jako: {output_filename}")
    # plt.show()


if __name__ == "__main__":
    analyze_hourly_comparison(20)
    analyze_hourly_comparison(30)
    analyze_hourly_comparison(130)
    # stats_a = get_mode_stats("A", 35)
